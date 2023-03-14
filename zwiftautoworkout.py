import json
import os
import random
import sys
import websocket

request_id = f'random-req-id-{random.randint(1, 100000000)}'
sub_id = f'random-sub-id-{random.randint(1, 100000000)}'

class AutoWorkout:
    def __init__(self):
        self.distance_m: float = None  # distance, in km
        self.time_secs: float = None      # zwift time

        self.wo_duration_secs: float = 122 + 2.0 + 0.5
        self.wo_end_secs: float = None

        self.ahk = "ahk.bat"

    def info(self):
        if self.distance_m is None:
            return ''
        
        sec = int(self.time_secs)
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60

        d = int(self.distance_m)
        info = f"{h}:{m:02d}:{s:02d} {self.distance_m/1000:7.4f}"
        return info

    def start_wo(self):
        print(f'\n{self.info()} Starting workout')
        self.wo_end_secs = self.time_secs + self.wo_duration_secs
        cmd = f"{self.ahk} start_workout.ahk"
        os.system(cmd)

    def end_wo(self):
        print(f'\n{self.info()} Ending workout')
        self.wo_end_secs =  None
        cmd = f"{self.ahk} end_workout.ahk"
        os.system(cmd)

    def update(self, distance: float, time: float):
        self.distance_m = distance
        self.time_secs = time

        if self.wo_end_secs is not None:
            # We're in workout
            if time >= self.wo_end_secs:
                self.end_wo()
        
        if self.wo_end_secs is None:
            # Not in workout
            excess = (distance/1000) - int(distance/1000)
            if excess < 0.050:
                self.start_wo()

        if self.wo_end_secs is not None:
            wo_info = f'WO {self.wo_end_secs - time:.0f} secs left'
        else:
            wo_info = ''

        print(f"\r{self.info()} {wo_info}", end='')
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
            print(json.dumps(me, sort_keys=True, indent=4))
            print('\n\n')

        d0 = get(me, 'state.distance')
        d1 = get(me, 'state.eventDistance')
        d = float(max(d0, d1))
        t = float(get(me, 'state.time'))
        aw.update(d, t)

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
                "event": "nearby", # watching, nearby, groups, etc...
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
    aw.end_wo()

if __name__ == "__main__":
    main()
    #test()
