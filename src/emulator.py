import sys
import common as device
from common import Buttons
import time

class Main:
    def __init__(self, app_path, process_name):
        self.app_path = app_path
        self.process_name = process_name
        self.buttons = Buttons("emulator") # 初始化点击按钮类

    # 运行雷电模拟器
    def start(self):
        device.restart_app(self.app_path,self.process_name)
        # 等待雷电模拟器启动完成
        device.sleep(0.3)
        print("雷电模拟器启动完成，开始自动化操作...")
        self.buttons.click("全选")
        device.sleep(0.3)
        self.buttons.click("批量操作")
        device.sleep(0.3)
        self.buttons.click("批量启动")

    # 搜索
    def search(self, id):
        self.buttons.click("下拉") # 去除焦点
        status = self.buttons.click("搜索") # 点击搜索框
        if status!=True:
            print("点击搜索框失败")
            return False
        device.clear() # 清楚内容
        value = f"雷电模拟器-{id}"
        device.write(value) # 输入内容
        return True
       
    
    # 批量启动新模拟器
    def batch_start(self, start_id, end_id):
        try :
            while True:
                device.open_app(self.app_path)
                self.search(start_id)
                print(f"正在启动第{start_id}个雷电模拟器...")
                device.sleep(1)
                self.buttons.click('启动')
                self.buttons.click("不在提示",1,True)
                device.sleep(1)
                self.buttons.click("不谢谢")
                start_id += 1
                if start_id  > end_id:
                    print("所有模拟器已打开")
                    break
            print("所有模拟器启动成功")   
        except :
            print('异常：终止执行')

    # 自动创建雷电模拟器
    def create(self):
        device.open_app(self.app_path)
        # 创建雷电模拟器
        # self.buttons.click("批量操作")
        # self.buttons.click("批量新增")
        # 配置雷电模拟器
        # self.buttons.click("全选",2)
        # self.buttons.click("批量操作")
        # self.buttons.click("批量设置")
        # self.buttons.click("分辨率")
        # self.buttons.click("内存")
        # self.buttons.click("其他设置")
        # self.buttons.click("退出选项")
        # self.buttons.click("保存设置")
        # self.buttons.click("确定")
        # 启动雷电模拟器
        data = device.read_json("cache.json")
        
        number = data["emulator_num"]
        start = number + 1
        end = start + data["batch_start_num"]
        end = 1
        self.batch_start(start, end)  

    def backup(self):
        data = device.read_json("cache.json")
        start= data["backup_start_id"]
        end = data["backup_end_id"]
        start, end = 3,3
        while start <= end:
            device.open_app(self.app_path)
            status = self.search(start)
            if status!=True:
                print(f"第{start}个模拟器操作异常")
                break
            device.sleep(1)
            self.buttons.click("备份/还原")
            self.buttons.click("备份")
            device.sleep(1)
            self.buttons.click("文件搜索")
            path = 'D:\\Program Files\\LDPlayer9\\test'
            device.paste(path)
            device.sleep(0.1)
            device.click_key("enter")
            device.sleep(0.1)
            break
            self.buttons.click("文件保存")
            start += 1
            device.sleep(1)
        print("备份完成:", end - data["backup_start_id"] + 1)
        
    
    def default(self):
        print("default")

    def switch(self,case):
        method = getattr(self, case,self.default)
        method()  
         


if __name__ == '__main__':
    app_path = "D:\\Program Files\\LDPlayer9\\dnmultiplayer.exe"
    process_name = "dnmultiplayer.exe"

    script_name = sys.argv[0]
    method = "default" # 调用默认方法
    if len(sys.argv) > 1:
        print("argv:", sys.argv[1:])
        method = sys.argv[1]
    else:
        method = 'backup' # dev模式使用
    emulator = Main(app_path, process_name) # 实例化模拟器类
    emulator.switch(method)
    


