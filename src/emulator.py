import sys
import common as device
from common import Buttons 

class Main:
    def __init__(self):
        config = device.read_json("config.json")
        self.app_path = config['emulator_path']
        self.process_name = config['emulator_process_name']
        self.buttons = Buttons("emulator") # 初始化点击按钮类
        self.config = config

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
       
    # 排列窗口
    def sort_win(self,status=True):
        if status==True:
            device.open_app(self.app_path)
            self.buttons.click("排列窗口")
            self.buttons.click("最小化雷电多开")
            device.sleep(1)

    # 批量启动新模拟器
    def batch_start(self, start_id, end_id):
        try :
            while start_id <= end_id:
                device.open_app(self.app_path)
                self.search(start_id)
                print(f"正在启动第{start_id}个雷电模拟器...")
                device.sleep(1)
                self.buttons.click('启动')
                self.buttons.click("不在提示",1,True)
                device.sleep(1)
                self.buttons.click("不谢谢")
                start_id += 1
            print("所有模拟器启动成功")   
        except :
            print('异常：终止执行')

    # 配置雷电模拟器
    def batch_setting(self):
        # self.buttons.click("全选",2)
        self.buttons.click("全选")
        self.buttons.click("批量操作")
        self.buttons.click("批量设置")
        self.buttons.click("分辨率")
        self.buttons.click("内存")
        self.buttons.click("其他设置")
        self.buttons.click("退出选项")
        self.buttons.click("保存设置")
        self.buttons.click("确定")
    
    # 开启同步
    def open_async(self,open_app=True):
        self.sort_win(open_app)
        first_op = self.config['emulator_coord_info_map']['first_op']
        device.click(first_op) # 点击第一个模拟器的选项
        self.buttons.click("同步选项")
        self.buttons.click("全选")
        self.buttons.click("开启同步")

    # 关闭同步
    def close_async(self,open_app=True):
        self.sort_win(open_app)
        first_op = self.config['emulator_coord_info_map']['first_op']
        device.click(first_op) # 点击第一个模拟器的选项
        self.buttons.click("同步选项")
        self.buttons.click("关闭同步")
        self.buttons.click("关闭同步窗口")
    
    # 安装应用
    def install(self,coord,app_name):
        device.click(coord) # 点击模拟器选项
        device.sleep(1)
        self.buttons.click("APK选项")
        device.sleep(1)
        self.buttons.click("选择APK")
        device.sleep(1)
        self.buttons.click("路径搜索")
        path = self.config['emulator_install_path']
        device.paste(path)
        device.sleep(0.1)
        device.click_key("enter")
        self.buttons.click("文件搜索")
        device.sleep(0.1)
        device.paste(app_name)
        device.sleep(0.1)
        self.buttons.click("文件打开")
        print(f"{app_name}安装中...")

    # 批量安装应用
    def batch_install(self,coord,app_names,open_app=True):
        self.sort_win(open_app)
        for app_name in app_names:
            self.install(coord,app_name)
            # 如果不是最后一个
            if app_name != app_names[-1]:
                device.sleep(1)
        print("批量安装操作完成.")

    # 应用设置
    def app_setting(self, open_app=True):
        self.sort_win(open_app)
        info_map = self.config['emulator_coord_info_map']
        ant = info_map['ant_app_xy']
        info = info_map['app_info_xy']
        device.drag(ant,info)
        device.sleep(3)
        
        # self.buttons.click("支付宝权限")
        device.click(info_map['app_auth'])
        device.sleep(1)
        # self.buttons.click("存储空间")
        # device.sleep(0.5)
        # self.buttons.click("电话")
        # device.sleep(0.5)
        # self.buttons.click("麦克风")
        # device.sleep(0.5)
        # self.buttons.click("通讯录")
        # device.sleep(0.5)
        # self.buttons.click("位置信息")
        # device.sleep(0.5)
        # self.buttons.click("相机")
        for i in range(info_map['auth_number']):
            y = info_map['auth_start'][1] + info_map['auth_height'] * i
            coord = (info_map['auth_start'][0],y)
            device.click(coord)
            # 如果不是最后一个权限
            device.sleep(1)
        device.click(info_map['first_task'])
        device.sleep(1)
        device.click(info_map['first_task_clear'])
        print("应用设置完成")

    # 自动创建雷电模拟器
    def create(self):
        device.restart_app(self.app_path,self.process_name)
        device.sleep(0.3)
        # # 创建雷电模拟器
        self.buttons.click("批量操作")
        self.buttons.click("批量新增")
        # # 配置雷电模拟器
        self.batch_setting()
        # # 启动雷电模拟器
        data = device.read_json("config.json")
        id = data["emulator_num"] # 最后一个雷电模拟器id
        start = id + 1 # 起始id
        end = id + data["batch_start_num"] # 结束id
        print("启动雷电模拟器：",start,"-",end)
        # self.batch_start(start, end)
        device.alert('请确认模拟器已启动...')
        self.sort_win()
        # 批量安装apk
        app_names = data['emulator_apk']
        first_op = data['emulator_coord_info_map']['first_op']
        # 遍历每个已开启的模拟器
        for i in range(data["batch_start_num"]):
            x = int(first_op[0]) + data['emulator_size'] * i
            coord_op= (x, int(first_op[1]))
            self.batch_install(coord_op, app_names, False)
            if i != data["batch_start_num"]-1:
                device.sleep(1)
        device.alert("请确认已安装完成...")
        self.open_async(False)
        device.sleep(1)
        self.app_setting(False)
        device.sleep(1)
        self.close_async(False)

    # 备份雷电模拟器
    def backup(self):
        data = device.read_json("config.json")
        start = data["backup_start_id"]
        end = data["backup_end_id"]
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
            self.buttons.click("路径搜索")
            path = 'D:\\Program Files\\LDPlayer9\\backup'
            device.paste(path)
            device.sleep(0.1)
            device.click_key("enter")
            device.sleep(0.1)
            self.buttons.click("文件保存")
            start += 1
            device.sleep(1)
        print("备份完成:", end - data["backup_start_id"] + 1)

    # 恢复雷电模拟器    
    def restore(self):
        data = device.read_json("config.json")
        start = data["backup_start_id"]
        end = data["backup_end_id"]
        # start, end = 29,29 # dev:数值相同还原单个
        while start <= end:
            device.open_app(self.app_path)
            status = self.search(start)
            if status!=True:
                print(f"第{start}个模拟器操作异常")
                break
            device.sleep(1)
            self.buttons.click("备份/还原")
            self.buttons.click("还原")
            device.sleep(1)
            self.buttons.click("路径搜索")
            path = 'D:\\Program Files\\LDPlayer9\\backup'
            device.paste(path)
            device.sleep(0.1)
            device.click_key("enter")
            self.buttons.click("文件搜索")
            device.sleep(0.1)
            app_name = f'雷电模拟器-{start}.ldbk'
            device.paste(app_name)
            device.sleep(0.1)
            self.buttons.click("文件打开")
            start += 1
        print("还原完成:", end - data["backup_start_id"] + 1)

    def default(self):
        print("default")

    def switch(self,case):
        method = getattr(self, case,self.default)
        method()  
         


if __name__ == '__main__': 
    script_name = sys.argv[0]
    method = "default" # 调用默认方法
    if len(sys.argv) > 1:
        print("argv:", sys.argv[1:])
        method = sys.argv[1]
    else:
        method = 'default' # dev模式使用
    emulator = Main() # 实例化模拟器类
    # emulator.buttons.click("最小化vscode")
    emulator.switch(method)
    


