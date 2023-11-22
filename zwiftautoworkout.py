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

MIN_DIST_BEFORE_WORKOUT_IN_UTURN_MODE = 30


if os.name=='nt':
    import winsound
else:
    class winsound:
        @staticmethod
        def Beep(freq: int, duration: int):
            pass


def warn():
    for i in range(3):
        winsound.Beep(2000, 50)


def prog(t: float) -> str:
    s = '|/-\\'
    return s[int(t) % len(s)]


class AutoWorkout:
    AHK_DELAY = 2

    def __init__(self, ftp, watt=None, uturn: bool = False, 
                 climb_distance: float = 0, lead_in: float=0):
        print(f"Profile FTP={ftp}")
        self.watt = watt
        self.uturn_mode = uturn
        self.uturn_done = False

        climb_distance = climb_distance or 0
        assert climb_distance < 50
        self.climb_distance_m = int(climb_distance * 1000)

        lead_in = lead_in or 0
        assert lead_in < 15  # lead in is in km
        self.lead_in_m = int(lead_in * 1000)

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
        if os.name=='nt':
            self.ahk: str = "ahk.bat"
        else:
            self.ahk: str = "echo ahk.bat"
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

    def _ahk(self, arg):
        """Invoke autohotkey"""
        winsound.Beep(2000, 100)
        cmd = f"{self.ahk} workout.ahk {arg}"
        os.system(cmd)
        winsound.Beep(1000, 100)

    def start_wo(self, watt, wo):
        """Start workout"""
        wo_idx = wo['idx'] + 1 # 1 based in AHK
        print(f'''{self.header()} Starting workout "{wo['name']}" (avg power: {watt}), dur: {wo['duration']}''')
        self._ahk(f"start {wo_idx}")
        self.start_time = self.time()
        self.end_time = self.start_time + wo['duration'] + self.AHK_DELAY + 1

    def cancel_wo(self):
        """Cancel (force end) current workout"""
        print(f'{self.header()} Cancelling workout')
        self.start_time, self.end_time =  None, None
        self.last_cancel_time = self.time()
        self.last_cancel_km = self.distance() // 1000
        self._ahk(f"cancel")

    def close_dlg(self):
        """Close workout dialog"""
        print(f'{self.header()} Closing dialog')
        self.start_time, self.end_time =  None, None
        self._ahk("close")

    def uturn(self):
        """Initiate U-Turn"""
        print(f'{self.header()} U-Turn')
        self._ahk(f"uturn")
        self.uturn_done = True

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

    def _next_climb_arch_m(self, distance: int) -> int:
        assert self.climb_distance_m
        arch_spacing = self.climb_distance_m // 10
        for i in range(10):
            next_arch = self.lead_in_m + (i+1)*arch_spacing
            if next_arch >= distance:
                break
        return next_arch

    def _can_start_wo(self, distance: int, est_end_distance: int) -> bool:
        if self.climb_distance_m:
            arch_spacing = self.climb_distance_m // 10
            next_arch = self._next_climb_arch_m(distance)

            return (
                # Don't start wo if we're in descent
                next_arch > distance and

                # Only start if we've passed the arch by some distance
                # (to allow spin wheel to complete)
                next_arch - distance < arch_spacing - 40 and

                # Only start if we can end WO before the arch
                est_end_distance < next_arch - 10 and

                # Get the km bonus (only start if WO can finish within the same km)
                (est_end_distance+10)//1000 == distance//1000 and

                # Not recently been cancelled
                self.time() - self.last_cancel_time > 5
            )
        else:
            return (
                (est_end_distance+10)//1000 == distance//1000 and
                not (distance//1000 == self.last_cancel_km and
                     self.time() - self.last_cancel_time <= 5
                    ) and
                (
                    # If we're in U-turn mode, wait some time before starting a workout to allow
                    # collecting arch bonus
                    not self.uturn_mode or 
                    (distance%1000) >= MIN_DIST_BEFORE_WORKOUT_IN_UTURN_MODE
                )
            )
        
    def _check_should_cancel_wo(self, distance: int, est_end_distance: int) -> bool:
        if self.climb_distance_m:
            next_arch = self._next_climb_arch_m(distance)
            return (
                    est_end_distance+10 >= next_arch
            )
        else:
            return (
                    (est_end_distance+10) // 1000 >  distance // 1000 and 
                    int(distance) % 1000 >= 950
            )

    def update(self, distance: float, time: float, power: float):
        """Update with the last distance, time, and power"""

        distance, time, power = int(distance), int(time), int(power)
        self.state.loc[time] = [distance, power]

        if len(self.state) > 200:
            self.state = self.state.tail(100)
        elif len(self.state) < 5:
            #print(f"\r{self.header()} {prog(time)}", end='')
            return

        avg_speed = self.get_avg_speed()
        nl = False
        est_end_distance = None

        if self.uturn_mode:
            if self.uturn_done:
                if (distance % 1000) < 300:
                    self.uturn_done = False
            else:
                # It took approx 3 seconds to make a U-turn
                turn_distance = int(distance + avg_speed * 3)
                if distance > 1000 and (turn_distance % 1000) >= 493:
                    self.uturn()
                elif distance > 1000 and (turn_distance % 1000) > 480 and (turn_distance % 1000) < 490:
                    warn()

        if self.is_in_workout():
            if time < self.end_time and self.end_time-time <= 2:
                warn()

            if time >= self.end_time:
                print('')
                self.close_dlg()
                nl = True
            else:
                est_end_distance = int(distance + avg_speed * (self.end_time - time))
                if self._check_should_cancel_wo(distance, est_end_distance):
                    print('')
                    print(f'{self.header()} Est. end for cur wo: {(est_end_distance+10)/1000:.3f}')
                    self.cancel_wo()
                    nl = True

        if not self.is_in_workout():
            watt = self.watt or self.get_avg_power()
            wo = self.get_matching_wo(watt)
            est_end_distance = int(distance + avg_speed * (wo['duration']+self.AHK_DELAY))
            # Check if new workout can end within this km and we're not recently cancelled
            if self._can_start_wo(distance, est_end_distance):
                if not nl:
                    print('')
                if self.uturn_mode:
                    # Spend powerups if we're in U-Turn mode, in case we're not using
                    # TT bike
                    self._ahk("spacebar")
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
            aw = AutoWorkout(ftp=data['athlete']['ftp'], watt=args.watt, uturn=args.uturn,
                             lead_in=args.leadin, climb_distance=args.climb)

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


def sim():
    interval = 1.0
    speed_kph = args.simspeed
    dist_interval = interval * speed_kph * 1000 / 3600

    distance = 0.0
    duration = 0.0
    power = args.watt or 111

    while True:
        msg = {
            'type': 'event',
            'success': True,
            'data': {
                'athlete': {
                    'ftp': 200,
                },
                'state': {
                    'distance': distance,
                    'time': duration,
                    'power': power,
                }
            }
        }
        doc = json.dumps(msg)
        on_message(None, doc)
        #time.sleep(interval)
        time.sleep(0.1)
        duration += interval
        distance += dist_interval


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
    parser.add_argument('--uturn', help='Perform U-turn at x.5 km')
    parser.add_argument('--leadin', help='Lead-in in km', type=float)
    parser.add_argument('--climb', help='Climb portal length in km', type=float)
    #parser.add_argument('--test', help='Run test', action='store', nargs='*')
    parser.add_argument('--sim', help='Simulation mode', action='store', nargs='*')
    parser.add_argument('--simspeed', help='Speed (kph)', type=float, default=20.0)
    
    args = parser.parse_args()

    if args.sim is not None:
        sim()
    else:
        main()
