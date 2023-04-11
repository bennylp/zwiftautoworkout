import argparse
import glob
import json
import os
import random
import sys
import websocket
import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET

request_id = f'random-req-id-{random.randint(1, 100000000)}'
sub_id = f'random-sub-id-{random.randint(1, 100000000)}'

class AutoWorkout:
    AHK_DELAY = 2

    def __init__(self, ftp, watt=None):
        self.watt = watt

        # scan workout files
        workouts = []
        for file in glob.glob('C:\\Users\\bennylp\\Documents\\Zwift\\Workouts\\890462\\*.zwo'):
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
        return f"{h}:{m:02d}:{s:02d} {self.distance()/1000:7.4f}"

    def get_matching_wo(self, watt=None):
        loc = self.workouts.index.get_loc(watt, method='nearest')
        return self.workouts.iloc[loc]

    def start_wo(self):
        """Start workout"""
        watt = self.watt or self.get_avg_power()
        wo = self.get_matching_wo(watt)
        wo_idx = wo['idx'] + 1 # 1 based in AHK

        print(f'\n{self.header()} Starting workout {wo["name"]} (power: {watt})')
        self.start_time = self.time()
        self.end_time = self.start_time + wo['duration'] + self.AHK_DELAY
        cmd = f"{self.ahk} workout.ahk start {wo_idx}"
        os.system(cmd)

    def cancel_wo(self):
        """Cancel (force end) current workout"""
        print(f'\n{self.header()} Cancelling workout')
        self.start_time, self.end_time =  None, None
        cmd = f"{self.ahk} workout.ahk cancel"
        os.system(cmd)

    def close_dlg(self):
        """Close workout dialog"""
        print(f'\n{self.header()} Closing dialog')
        self.start_time, self.end_time =  None, None
        cmd = f"{self.ahk} workout.ahk close"
        os.system(cmd)

    def get_avg_speed(self, secs: int = 5) -> float:
        """Get current avg speed for the past secs seconds, in meter/sec"""
        df = self.state.tail(secs)
        d_dist = (df['distance'].iloc[-1] - df['distance'].iloc[0]) / 1
        d_time = (df.index[-1] - df.index[0]) / 1
        return d_dist / d_time

    def get_avg_power(self, secs: int = 30) -> int:
        """Get current avg power for the past secs seconds, in watt"""
        ewm = self.state['power'].ewm(span=secs, min_periods=1)
        avg = ewm.mean().iloc[-1]
        return None if pd.isna(avg) else int(avg)

    def update(self, distance: float, time: float, power: float):
        """Update with the last distance, time, and power"""

        distance, time, power = int(distance), int(time), int(power)
        self.state.loc[time] = [distance, power]

        if len(self.state) > 200:
            self.state = self.state.tail(100)
        elif len(self.state) < 5:
            return

        avg_speed = self.get_avg_speed()

        if self.is_in_workout():
            if time >= self.end_time:
                self.close_dlg()
            else:
                est_end_distance = int(distance + avg_speed * (self.end_time - time) + 20)
                if (est_end_distance % 1000) <  (distance % 1000):
                    # Workout will finish in new kilometer.
                    # Cancel it to get kilometer bonus
                    self.cancel_wo()

        if not self.is_in_workout():
            wo = self.get_matching_wo(self.watt or self.get_avg_power())
            est_end_distance = int(distance + avg_speed * (wo['duration']+self.AHK_DELAY) + 10)
            if (est_end_distance % 1000) >  (distance % 1000):
                # Workout can finish within this kilometer
                # Start workout
                self.start_wo()

        if self.is_in_workout():
            wo_info = f'WO {self.end_time - time:.0f} secs left '
        else:
            wo_info = ''

        print(f"\r{self.header()} {wo_info}", end='')
        sys.stdout.flush()


def on_message(ws, raw_msg):
    msg = json.loads(raw_msg)
    if msg['type'] == 'response':
        if not msg['success']:
            raise Exception('subscribe request failure')
    elif msg['type'] == 'event' and msg['success']:
        data = msg['data']
        #print('')
        #print(json.dumps(data, sort_keys=True, indent=4))
        #sys.exit(0)
        me = data
        if not me:
            print(".", end='')
            sys.stdout.flush()
            return

        def get(d, path):
            keys = path.split('.')
            for key in keys:
                try:
                    d = d[key]
                except Exception as e:
                    print(f'{str(e)}: {key} in {path}')
                    raise

            return d

        def show(d, path):
            print(f'{path}: {get(d, path)}')

        if False:
            show(me, "lap.activeTime")
            show(me, "lap.elapsedTime")
            show(me, "state.distance")
            show(me, "state.eventDistance")
            show(me, "state.time")
            show(me, "stats.activeTime")
            show(me, "stats.activeTime")
            show(me, "stats.elapsedTime")
            print('')
            #print(json.dumps(me, sort_keys=True, indent=4))
            print('\n\n')

        d0 = get(me, 'state.distance')
        d1 = get(me, 'state.eventDistance')
        d = float(max(d0, d1))
        t = float(get(me, 'state.time'))
        p = float(get(me, 'state.power'))
        aw.update(d0, t, p)

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
                #"event": "watching",
                "subId": sub_id
            }
        }
    }))



def main(url):
    #websocket.enableTrace(True)
    if not url:
        host = "ws://127.0.0.1:1080/api/ws/events"
    else:
        host = f'{url}/api/ws/events'
    print("Connecting to:", host)
    ws = websocket.WebSocketApp(host,
                                on_open = on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever()


def test():
    aw = AutoWorkout(ftp=190)
    aw.update(1000, 1, 100)
    aw.update(1001, 2, 101.5)
    aw.update(1002, 3, 99)
    aw.update(1004, 4, 100)
    aw.update(1005, 5, 101)
    aw.update(1006, 6, 100)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='ZwiftAutoWorkout')
    parser.add_argument('--ftp', type=int, help='Set player FTP', required=True)
    parser.add_argument('--watt', type=int, help='Use this watt for workout')
    parser.add_argument('--url', help='Sauce4Zwift web server URL')
    
    args = parser.parse_args()

    aw = AutoWorkout(ftp=args.ftp, watt=args.watt)
    main(args.url)
    #test()
