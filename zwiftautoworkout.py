import argparse
import glob
import json
import os
import random
import sys
import websocket
import pandas as pd
import numpy as np
import time
import xml.etree.ElementTree as ET
from typing import Literal

request_id = f'random-req-id-{random.randint(1, 100000000)}'
sub_id = f'random-sub-id-{random.randint(1, 100000000)}'
aw = None
args = None

class AutoWorkout:
    AHK_DELAY = 2

    def __init__(self, ftp, watt=None):
        print(f"Profile FTP={ftp}")
        self.watt = watt

        # scan workout files
        workouts = []
        # 'C:\\Users\\bennylp\\Documents\\Zwift\\Workouts\\890462\\*.zwo'
        for file in glob.glob('workouts/*.zwo'):
            tree = ET.parse(file)
            root = tree.getroot()
            st = root.find('sportType').text
            if st != 'bike':
                continue
            it = root.find('workout').find('IntervalsT')
            wo = dict(duration=int(it.attrib['Repeat']) * 
                               (int(it.attrib['OnDuration']) + 
                                int(it.attrib['OffDuration'])),
                      power=int(float(it.attrib['OnPower']) * ftp),
                      name=root.find('name').text,
                     )
            workouts.append(wo)
        
        self.workouts = pd.DataFrame(data=workouts).set_index('power')
        self.workouts = self.workouts.sort_values('name')
        self.workouts['idx'] = range(len(self.workouts))
        self.workouts = self.workouts.head(8)
        print('Detected workouts (max=8):')
        print(self.workouts)

        # init state dataframe
        self.state = pd.DataFrame(data={'time': [0], 
                                        'distance': [0],
                                        'power': [0],
                                        },
                                  columns=['time', 'distance', 'power'],
                                  ).set_index('time')
        self.start_time: int = None
        self.end_time: int = None
        self.ahk: str = "ahk.bat"
        self.last_cancel_time = 0
        self.last_cancel_km = -1

    def is_in_workout(self) -> bool:
        return self.end_time is not None
    
    def time(self) -> int:
        """Return current time, in seconds"""
        return self.state.index[-1] if len(self.state) else 0

    def distance(self) -> int:
        """Return current distance, in meters"""
        return self.state['distance'].iloc[-1] if len(self.state) else 0
    
    def header(self) -> str:
        sec = self.time()
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60

        avg_speed = self.get_avg_speed(output='kph')
        avg_power = self.get_avg_power()
        return f"{h}:{m:02d}:{s:02d} {self.distance()/1000:.3f} {avg_speed:4.1f}kph {avg_power:3.0f}w"

    def get_matching_wo(self, watt=None):
        loc = self.workouts.index.get_loc(watt, method='nearest')
        return self.workouts.iloc[loc]

    def start_wo(self, watt, wo):
        """Start workout"""
        wo_idx = wo['idx'] + 1 # 1 based in AHK
        print(f'''{self.header()} Starting workout "{wo['name']}" (avg power: {watt})''')
        self.start_time = self.time()
        self.end_time = self.start_time + wo['duration'] + self.AHK_DELAY
        cmd = f"{self.ahk} workout.ahk start {wo_idx}"
        os.system(cmd)

    def cancel_wo(self):
        """Cancel (force end) current workout"""
        print(f'{self.header()} Cancelling workout')
        self.start_time, self.end_time =  None, None
        cmd = f"{self.ahk} workout.ahk cancel"
        self.last_cancel_time = self.time()
        self.last_cancel_km = self.distance() // 1000
        os.system(cmd)

    def close_dlg(self):
        """Close workout dialog"""
        print(f'{self.header()} Closing dialog')
        self.start_time, self.end_time =  None, None
        cmd = f"{self.ahk} workout.ahk close"
        os.system(cmd)

    def get_avg_speed(self, secs: int = 5, output: Literal['mps', 'kph', 'mph']='mps') -> float:
        """Get current avg speed for the past secs seconds, in meter per second,
        km/h, or miles/h"""
        df = self.state.tail(secs+1)
        d_dist = (df['distance'].iloc[-2] - df['distance'].iloc[0]) / 1
        d_time = (df.index[-2] - df.index[0]) / 1
        mps = d_dist / max(d_time,1)  # meter per second
        return (mps if output=='mps' else
                mps*3600/1000 if output=='kph' else
                mps*3600/1609.344)

    def get_avg_power(self, secs: int = 5) -> int:
        """Get current avg power for the past secs seconds, in watt"""
        if True:
            avg = self.state['power'].rolling(secs, min_periods=1).mean().iloc[-1]
        else:
            avg = self.state['power'].ewm(span=secs, min_periods=1).mean().iloc[-1]
        return None if pd.isna(avg) else int(avg)

    def update(self, distance: float, time: float, power: float):
        """Update with the last distance, time, and power"""

        distance, time, power = int(distance), int(time), int(power)
        self.state.loc[time] = [distance, power]

        def prog(t: float) -> str:
            s = '|/-\\'
            return s[int(t) % len(s)]

        if len(self.state) > 200:
            self.state = self.state.tail(100)
        elif len(self.state) < 5:
            print(f"\r{self.header()} {prog(time)}", end='')
            return

        avg_speed = self.get_avg_speed()
        nl = False
        est_end_distance = None

        if self.is_in_workout():
            if time >= self.end_time:
                print('')
                self.close_dlg()
                nl = True
            else:
                est_end_distance = int(distance + avg_speed * (self.end_time - time))
                if ((est_end_distance+10)//1000) >  (distance//1000) and int(distance)%1000 >= 950:
                    print('')
                    print(f'{self.header()} Est. end for cur wo: {(est_end_distance+10)/1000:.3f}')
                    self.cancel_wo()
                    nl = True

        if not self.is_in_workout():
            watt = self.watt or self.get_avg_power()
            wo = self.get_matching_wo(watt)
            est_end_distance = int(distance + avg_speed * (wo['duration']+self.AHK_DELAY))
            # Check if new workout can end within this km and we're not recently cancelled
            if ((est_end_distance+10)//1000 == distance//1000 and not
                (distance//1000 == self.last_cancel_km and
                 self.time() - self.last_cancel_time <= 5
                )):
                if not nl:
                    print('')
                self.start_wo(watt, wo)

        if self.is_in_workout():
            wo_info = f'{self.end_time - time:.0f} secs left [est. end: {est_end_distance/1000:.3f}]'
        else:
            wo_info = prog(time)

        print(f"\r{self.header()} {wo_info} ", end='')
        sys.stdout.flush()


def on_message(ws, raw_msg):
    global aw

    msg = json.loads(raw_msg)
    if msg['type'] == 'response':
        if not msg['success']:
            raise Exception('subscribe request failure')
    elif msg['type'] == 'event' and msg['success']:
        data = msg['data']
        if aw is None:
            aw = AutoWorkout(ftp=data['athlete']['ftp'], watt=args.watt)

        d = float(data['state']['distance'])
        t = float(data['state']['time'])
        p = float(data['state']['power'])
        aw.update(d, t, p)

def on_error(ws, error):
    print("socket error", error)


def on_close(ws, status_code, msg):
    print("socket closed", status_code, msg)


def on_open(ws):
    print('Connected.')
    ws.send(json.dumps({
        "type": "request",
        "uid": request_id,
        "data": {
            "method": "subscribe",
            "arg": {
                "event": "athlete/self", # watching, nearby, groups, etc...
                "subId": sub_id
            }
        }
    }))



def main():
    #websocket.enableTrace(True)
    if not args.url:
        host = "ws://127.0.0.1:1080/api/ws/events"
    else:
        host = f'{args.url}/api/ws/events'
    print("Connecting to:", host)
    ws = websocket.WebSocketApp(host,
                                on_open = on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever()


def test():
    global aw
    ftp = 190
    aw = AutoWorkout(ftp=ftp)
    aw.AHK_DELAY = 0
    aw.ahk = 'true'

    first = [
        (40,4),   # initial wait
        (330,32),
        (300,32),
        (330,32), # the last workout will be cancelled
    ]
    assert sum([e[0] for e in first])==1000

    loop = [
        (150,16), (180,16),   # workout
        (200,16), (130, 16),  # workout
        (130, 18), (210, 14), # this workout will be cancelled
    ]
    assert sum([e[0] for e in loop])==1000
    assert sum([e[1] for e in loop])==32*3
    specs = first + loop * 5

    distance = 0
    t = 0
    for delta, dur in specs:
        speed = delta / dur
        kph = speed / 1000 * 3600
        for _ in range(dur):
            aw.update(distance, t, ftp / 2 * kph / 20)
            distance += speed
            t += 1
            time.sleep(0.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='ZwiftAutoWorkout')
    parser.add_argument('--watt', type=int, help='Lock workout at this power')
    parser.add_argument('--url', help='Explicit Sauce4Zwift web server URL (start with ws://)')
    parser.add_argument('--test', help='Run test', action='store', nargs='*')
    
    args = parser.parse_args()

    if args.test is not None:
        test()
    else:
        main()
