import json
import os
import random
import sys
import websocket
import pandas as pd

request_id = f'random-req-id-{random.randint(1, 100000000)}'
sub_id = f'random-sub-id-{random.randint(1, 100000000)}'

class AutoWorkout:
    WO_DURATION = 32
    AHK_DELAY = 1.5

    def __init__(self):
        self.state = pd.DataFrame(columns=['time', 'distance'],
                                  dtype=[int,int]).set_index('time')
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

    def start_wo(self):
        """Start workout"""
        print(f'\n{self.header()} Starting workout')
        self.start_time = self.time()
        self.end_time = self.start_time + self.WO_DURATION + self.AHK_DELAY
        cmd = f"{self.ahk} workout.ahk start"
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

    def update(self, distance: float, time: float):
        """Update with the last distance and time"""

        distance, time = int(distance), int(time)
        self.state.loc[time, 'distance'] = distance

        if len(self.state) > 200:
            self.state = self.state.tail(100)

        if self.is_in_workout():
            if time >= self.end_time:
                self.close_dlg()
            else:
                avg_speed = self.get_avg_speed()
                est_end_distance = int(distance + avg_speed * (self.end_time - time) + 10)
                if (est_end_distance % 1000) <  (distance % 1000):
                    # Workout will finish in new kilometer.
                    # Cancel it to get kilometer bonus
                    self.cancel_wo()

        if not self.is_in_workout():
            avg_speed = self.get_avg_speed()
            est_end_distance = int(distance + avg_speed * (self.WO_DURATION+self.AHK_DELAY) + 10)
            if (est_end_distance % 1000) >  (distance % 1000):
                # Workout can finish within this kilometer
                # Start workout
                self.start_wo()

        if self.is_in_workout():
            wo_info = f'WO {self.end_time - time:.0f} secs left  '
        else:
            wo_info = '          '

        print(f"\r{self.header()} {wo_info}", end='')
        sys.stdout.flush()


aw = AutoWorkout()


def on_message(ws, raw_msg):
    msg = json.loads(raw_msg)
    if msg['type'] == 'response':
        if not msg['success']:
            raise Exception('subscribe request failure')
    elif msg['type'] == 'event' and msg['success']:
        data = msg['data']
        #print()
        #print(json.dumps(data, sort_keys=True, indent=4))
        me = None
        for d in data:
            if d["athleteId"] == 890462:
                me = d
                break
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
        aw.update(d0, t)

def on_error(ws, error):
    print("socket error", error)


def on_close(ws, status_code, msg):
    print("socket closed", status_code, msg)


def on_open(ws):
    ws.send(json.dumps({
        "type": "request",
        "uid": request_id,
        "data": {
            "method": "subscribe",
            "arg": {
                #"event": "nearby", # watching, nearby, groups, etc...
                "event": "self",
                "subId": sub_id
            }
        }
    }))



def main():
    #websocket.enableTrace(True)
    if len(sys.argv) < 2:
        host = "ws://localhost:1080/api/ws/events"
    else:
        host = sys.argv[1]
    print("Connecting to:", host)
    ws = websocket.WebSocketApp(host,
                                on_open = on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever()


def test():
    aw.distance_m = 0
    aw.time_secs = 0
    aw.close_dlg()

if __name__ == "__main__":
    main()
    #test()
