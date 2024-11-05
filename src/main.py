# -*- coding: utf-8 -*-
from datetime import datetime
import scheduler
import sys
import common.device as device


import os
# 获取当前工作目录
current_dir = os.getcwd()
print("当前工作目录：", current_dir)

def test_time():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("当前时间：",current_time)
    
# 输出当前日期和时间
def main():
    print("按 ESC 键停止进程任务...")
    # 定时任务
    # scheduler.start(start,0,0,0)
    test_time()
    import emulator.test as test

class Progress:
    # def __init__(self):
    #     pass
    def emulator_start(self):
        import emulator.start as start
        start.main()

    def default(self):
        print("default")
    def switch(self, case):
        method = getattr(self, case, self.default)
        method() 

if __name__ == "__main__":
    script_name = sys.argv[0]
    print("Script name:", script_name,sys.argv[1:])
    if len(sys.argv) > 1:
        case = sys.argv[1]
        progress = Progress()
        progress.switch(case)
    else:
        main()
    
    