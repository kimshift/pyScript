# -*- coding: utf-8 -*-
"""雷电模拟器批量自动化 —— 业务编排层。

后端策略（可在 config.json 用 "backend" 切换）
--------------------------------------------
* "cli"（默认）：能用官方 `ldconsole` 的动作用命令行完成，
  只有「同步器开关」「模拟器内应用权限」这类没有接口的步骤才走 GUI。
* "gui"：保留重构前的纯图像匹配 + 点击流程，作为回滚开关。

两套后端共用同一份 config.json 与按钮映射，切换不需要改代码。
"""

import os
import time

from kit.log import get_logger
from tools.ld_emulator import common as device
from tools.ld_emulator.backends import LdConsole, LdConsoleError
from tools.ld_emulator.common import Buttons

log = get_logger("ld_emulator")


class Main:
    def __init__(self, backend: str | None = None):
        self.config = device.read_config()
        self.app_path = self.config['emulator_path']
        self.process_name = self.config['emulator_process_name']

        self.backend = (backend or self.config.get('backend', 'cli')).lower()
        self.ld = None
        if self.backend == 'cli':
            try:
                self.ld = LdConsole.from_emulator_path(self.app_path)
                log.info("后端：ldconsole（%s）", self.ld.exe)
            except LdConsoleError as exc:
                log.warning("CLI 后端不可用（%s），本次回退到 GUI", exc)
                self.backend = 'gui'
        if self.backend == 'gui':
            log.info("后端：GUI（图像匹配 + 鼠标点击）")

        self.use_cli = self.backend == 'cli'
        self._new_ids: list[int] = []
        self.buttons = Buttons("emulator")  # 初始化点击按钮类

    # ================= 查询 =================

    def info(self):
        """列出所有实例（不操作任何东西）。"""
        if not self.use_cli:
            print("info 需要 CLI 后端（config.json 里 backend 设为 cli）")
            return
        instances = self.ld.list2()
        if not instances:
            print("没有找到模拟器实例")
            return
        print(f"{'index':>5}  {'状态':<6} {'分辨率':<16} 标题")
        for inst in instances:
            state = "运行中" if inst.running else "已停止"
            print(f"{inst.index:>5}  {state:<6} {inst.width}x{inst.height}@{inst.dpi:<6} {inst.title}")

    # ================= 启动 =================

    def start(self):
        if self.use_cli:
            return self._start_cli()
        device.restart_app(self.app_path, self.process_name)
        # 等待雷电模拟器启动完成
        device.sleep(0.3)
        print("雷电模拟器启动完成，开始自动化操作...")
        self.buttons.click("全选")
        device.sleep(0.3)
        self.buttons.click("批量操作")
        device.sleep(0.3)
        self.buttons.click("批量启动")

    def _start_cli(self):
        device.open_app(self.app_path)
        instances = self.ld.list2()
        stopped = [i for i in instances if not i.running]
        if not stopped:
            print(f"没有需要启动的实例（共 {len(instances)} 个，均已在运行）")
            return
        print(f"批量启动 {len(stopped)} 个实例...")
        for inst in stopped:
            self.ld.launch(inst.index)
        print("启动命令已全部下发（模拟器在后台慢慢起来，不阻塞）")

    # ================= GUI 兜底动作（保留原逻辑） =================

    # 搜索
    def search(self, id):
        self.buttons.click("下拉")  # 去除焦点
        status = self.buttons.click("搜索")  # 点击搜索框
        if status != True:
            print("点击搜索框失败")
            return False
        device.clear()  # 清楚内容
        value = f"-{id}"
        device.write(value)  # 输入内容
        return True

    # 排列窗口
    def sort_win(self, status=True):
        if self.use_cli:
            self.ld.sort_wnd()
            device.sleep(1)
            if status == True:
                device.open_app(self.app_path)
                self.buttons.click("最小化雷电多开")
                device.sleep(1)
            return
        if status == True:
            device.open_app(self.app_path)
            self.buttons.click("排列窗口")
            device.sleep(1)
            self.buttons.click("最小化雷电多开")
            device.sleep(1)

    # ================= 批量启动（按 ID 范围） =================

    def batch_start(self, start_id, end_id):
        if self.use_cli:
            return self._batch_start_cli(start_id, end_id)
        try:
            while start_id <= end_id:
                device.open_app(self.app_path)
                self.search(start_id)
                print(f"正在启动第{start_id}个雷电模拟器...")
                device.sleep(2)
                self.buttons.click('启动')
                self.buttons.click("不在提示", 1, True)
                device.sleep(1)
                self.buttons.click("不谢谢")
                start_id += 1
            print("所有模拟器启动成功")
        except Exception as e:
            print(f"异常：终止执行 -> {e}")

    def _batch_start_cli(self, start_id, end_id):
        ids = list(range(int(start_id), int(end_id) + 1))
        print(f"批量启动：{ids[0]} - {ids[-1]}")
        failed = []
        for i in ids:
            if device.hotkey.should_stop():
                print("检测到 F8，已中断")
                break
            try:
                self.ld.launch(i)
            except LdConsoleError as exc:
                log.warning("启动 %s 失败：%s", i, exc)
                failed.append(i)
        if failed:
            print(f"以下实例启动失败：{failed}")
        else:
            print("启动命令已全部下发")

    # ================= 批量设置（分辨率/内存） =================

    def batch_setting(self):
        # 每个步骤之间加间隔，避免点击过快导致 UI 未就绪而漏点
        self.buttons.click("全选")
        device.sleep(0.3)
        self.buttons.click("批量操作")
        device.sleep(0.3)
        self.buttons.click("批量设置")
        device.sleep(0.3)
        self.buttons.click("分辨率")
        device.sleep(0.3)
        self.buttons.click("内存")
        device.sleep(0.3)
        self.buttons.click("其他设置")
        device.sleep(0.3)
        self.buttons.click("退出选项")
        device.sleep(0.3)
        self.buttons.click("保存设置")
        device.sleep(0.3)
        self.buttons.click("确定")

    def _apply_settings_cli(self, ids):
        """用 ldconsole modify 替代 batch_setting 的 9 步点击。

        只有在 config.json 里显式配置了 emulator_resolution / emulator_memory
        时才会修改对应项；没配置就跳过并提示，绝不猜值。
        """
        resolution = self.config.get('emulator_resolution')
        memory = self.config.get('emulator_memory')
        if not resolution and not memory:
            log.warning(
                "未配置 emulator_resolution / emulator_memory，跳过参数修改"
                "（实例将使用雷电默认值）。需要的话在 config.json 里补上，例如 "
                '"emulator_resolution": "1080,1920,480"'
            )
            return
        for i in ids:
            self.ld.modify(i, resolution=resolution, memory=memory)

    # ================= 同步器（无 CLI，必须 GUI） =================

    # 开启同步
    def open_async(self, open_app=True):
        self.sort_win(open_app)
        first_op = self.config['emulator_coord_info_map']['first_op']
        device.click(first_op)  # 点击第一个模拟器的选项
        self.buttons.click("同步选项")
        self.buttons.click("全选")
        self.buttons.click("开启同步")

    # 关闭同步
    def close_async(self, open_app=True):
        self.sort_win(open_app)
        device.sleep(1)
        first_op = self.config['emulator_coord_info_map']['first_op']
        device.click(first_op)  # 点击第一个模拟器的选项
        self.buttons.click("同步选项")
        device.sleep(1)
        self.buttons.click("关闭同步")
        self.buttons.click("关闭同步窗口")

    # ================= 安装 APK =================

    # 安装应用（GUI：单实例，靠坐标）
    def install(self, coord, app_name):
        device.click(coord)  # 点击模拟器选项
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

    # 批量安装应用（GUI）
    def batch_install(self, coord, app_names, open_app=True):
        self.sort_win(open_app)
        device.sleep(1)
        for app_name in app_names:
            self.install(coord, app_name)
            # 如果不是最后一个
            if app_name != app_names[-1]:
                device.sleep(1)
        print("批量安装操作完成.")

    def batch_install_fixed(self):
        if self.use_cli:
            return self._batch_install_cli()
        # 批量安装配置文件内的应用
        data = device.read_config()
        app_names = data['emulator_apk']
        first_op = data['emulator_coord_info_map']['first_op']
        # 遍历每个已开启的模拟器
        for i in range(data["batch_start_num"]):
            x = int(first_op[0]) + data['emulator_size'] * i
            coord_op = (x, int(first_op[1]))
            self.batch_install(coord_op, app_names, False)
            if i != data["batch_start_num"] - 1:
                device.sleep(1)

    def _install_targets(self):
        """确定要给哪些实例装包。

        优先用本次 create 新建的 id；单独跑 create_con 时，
        取「正在运行的实例」中 index 最大的 batch_start_num 个（即最近创建的）。
        """
        n = int(self.config.get('batch_start_num', 1))
        if self._new_ids:
            return self._new_ids[:n] if len(self._new_ids) >= n else self._new_ids
        running = [i for i in self.ld.list2() if i.running]
        running.sort(key=lambda x: x.index, reverse=True)
        return [i.index for i in running[:n]]

    def _batch_install_cli(self):
        app_names = self.config['emulator_apk']
        install_dir = self.config['emulator_install_path']
        targets = self._install_targets()
        if not targets:
            print("没有可安装的目标实例（没有运行中的模拟器）")
            return
        print(f"CLI 批量装包：{len(targets)} 个实例 × {len(app_names)} 个 APK")
        for target in targets:
            if device.hotkey.should_stop():
                print("检测到 F8，已中断")
                return
            for app_name in app_names:
                apk = os.path.join(install_dir, app_name)
                try:
                    self.ld.install_app(target, apk)
                except LdConsoleError as exc:
                    log.warning("装包失败 %s -> %s：%s", app_name, target, exc)
        print("批量安装操作完成.")

    # ================= 应用设置（模拟器内，必须 GUI） =================

    def app_setting(self, open_app=True):
        self.sort_win(open_app)
        info_map = self.config['emulator_coord_info_map']
        ant = info_map['ant_app_xy']
        info = info_map['app_info_xy']
        device.drag(ant, info)
        device.sleep(3)

        device.click(info_map['app_auth'])
        device.sleep(2)
        for i in range(info_map['auth_number']):
            y = info_map['auth_start'][1] + info_map['auth_height'] * i
            coord = (info_map['auth_start'][0], y)
            device.click(coord)
            # 如果不是最后一个权限
            device.sleep(1)
        device.click(info_map['first_task'])
        device.sleep(1)
        device.click(info_map['first_task_clear'])
        print("应用设置完成")

    # ================= 配置回写 =================

    def update_config(self):
        data = device.read_config()
        id = data["emulator_end_id"]  # 最后一个雷电模拟器id
        num = data["batch_start_num"]  # 批量启动数量
        data["emulator_end_id"] = id + num
        device.write_json(device.CONFIG_PATH, data)
        print("配置更新完成")

    # ================= 创建 =================

    def create(self):
        if self.use_cli:
            return self._create_cli()
        device.restart_app(self.app_path, self.process_name)
        device.sleep(1)
        # # 创建雷电模拟器
        self.buttons.click("批量操作")
        self.buttons.click("批量新增")
        # # 配置雷电模拟器
        self.batch_setting()
        # # 启动雷电模拟器
        data = device.read_config()
        id = data["emulator_end_id"]  # 最后一个雷电模拟器id
        start = id + 1  # 起始id
        end = id + data["batch_start_num"]  # 结束id
        print("启动雷电模拟器：", start, "-", end)
        self.batch_start(start, end)  # 启动模拟器
        device.sleep(3)
        self.sort_win()
        device.sleep(1)
        self.batch_install_fixed()  # 安装应用
        device.sleep(5)
        self.open_async(False)  # 开启模拟器同步
        device.sleep(1)
        self.app_setting(False)  # 应用设置
        device.sleep(1)
        self.close_async(False)  # 关闭模拟器同步
        self.update_config()  # 更新配置信息

    def _create_cli(self):
        num = int(self.config['batch_start_num'])
        last_id = int(self.config['emulator_end_id'])
        ids = list(range(last_id + 1, last_id + num + 1))
        prefix = self.config.get('emulator_name_prefix', '雷电-')
        self._new_ids = ids

        print(f"CLI 创建 {num} 个实例：{ids[0]} - {ids[-1]}")
        for i in ids:
            if device.hotkey.should_stop():
                print("检测到 F8，已中断创建")
                return
            self.ld.add(f"{prefix}{i}")
        device.sleep(1)  # 等 list2 反映新实例

        # 分辨率 / 内存
        self._apply_settings_cli(ids)

        # 启动
        for i in ids:
            self.ld.launch(i)
        print("等待实例启动完成...")
        self._wait_running(ids, timeout=180)
        device.sleep(3)

        # 排列窗口 + 装包
        self.sort_win()
        device.sleep(1)
        self._batch_install_cli()
        device.sleep(5)

        # 以下两步没有 CLI 接口，走 GUI
        self.open_async(False)   # 开启同步
        device.sleep(1)
        self.app_setting(False)  # 应用设置
        device.sleep(1)
        self.close_async(False)  # 关闭同步

        self.update_config()

    def _wait_running(self, ids, timeout=180):
        """轮询 list2 直到这些 id 全部 running（或超时）。"""
        pending = set(str(i) for i in ids)
        deadline = time.time() + timeout
        while pending and time.time() < deadline:
            snapshot = self.ld.list2()
            running_titles = [x.title for x in snapshot if x.running]
            pending = {p for p in pending if not any(t.endswith(p) for t in running_titles)}
            if pending:
                if device.hotkey.should_stop():
                    print("检测到 F8，停止等待")
                    return
                device.sleep(2)
        if pending:
            print(f"以下实例启动超时（{timeout}s）：{sorted(pending)}")
        else:
            print(f"{len(ids)} 个实例已全部进入运行状态")

    # ================= 续跑（已创建，只装包+同步+权限） =================

    def create_con(self):
        self.sort_win()
        device.sleep(1)
        self.batch_install_fixed()  # 安装应用
        device.sleep(5)
        self.open_async(False)  # 开启模拟器同步
        device.sleep(1)
        self.app_setting(False)  # 应用设置
        device.sleep(1)
        self.close_async(False)  # 关闭模拟器同步
        self.update_config()  # 更新配置信息

    # ================= 备份 / 还原 =================

    def backup(self):
        if self.use_cli:
            return self._backup_cli()
        data = device.read_config()
        start = data["backup_start_id"]
        end = data["backup_end_id"]
        backup_path = data.get("backup_path", "D:\\Program Files\\LDPlayer9\\backup")
        while start <= end:
            device.open_app(self.app_path)
            status = self.search(start)
            if status != True:
                print(f"第{start}个模拟器操作异常")
                break
            device.sleep(1)
            self.buttons.click("备份/还原")
            self.buttons.click("备份")
            device.sleep(1)
            self.buttons.click("路径搜索")
            device.paste(backup_path)
            device.sleep(0.1)
            device.click_key("enter")
            device.sleep(0.1)
            self.buttons.click("文件保存")
            start += 1
            device.sleep(1)
        print("备份完成:", end - data["backup_start_id"] + 1)

    def _backup_cli(self):
        data = self.config
        start, end = int(data["backup_start_id"]), int(data["backup_end_id"])
        backup_dir = data.get("backup_path", "")
        if not backup_dir:
            print("config.json 未配置 backup_path")
            return
        print(f"CLI 备份 {start} - {end} -> {backup_dir}")
        ok = 0
        for i in range(start, end + 1):
            if device.hotkey.should_stop():
                print("检测到 F8，已中断")
                break
            try:
                self.ld.backup(i, os.path.join(backup_dir, f"雷电模拟器-{i}.ldbk"))
                ok += 1
            except LdConsoleError as exc:
                log.warning("备份 %s 失败：%s", i, exc)
        print(f"备份完成：{ok}/{end - start + 1}")

    def restore(self):
        if self.use_cli:
            return self._restore_cli()
        data = device.read_config()
        start = data["backup_start_id"]
        end = data["backup_end_id"]
        backup_path = data.get("backup_path", "D:\\Program Files\\LDPlayer9\\backup")
        while start <= end:
            device.open_app(self.app_path)
            status = self.search(start)
            if status != True:
                print(f"第{start}个模拟器操作异常")
                break
            device.sleep(1)
            self.buttons.click("备份/还原")
            self.buttons.click("还原")
            device.sleep(1)
            self.buttons.click("路径搜索")
            device.paste(backup_path)
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

    def _restore_cli(self):
        data = self.config
        start, end = int(data["backup_start_id"]), int(data["backup_end_id"])
        backup_dir = data.get("backup_path", "")
        print(f"CLI 还原 {start} - {end} <- {backup_dir}")
        ok = 0
        for i in range(start, end + 1):
            if device.hotkey.should_stop():
                print("检测到 F8，已中断")
                break
            try:
                self.ld.restore(i, os.path.join(backup_dir, f"雷电模拟器-{i}.ldbk"))
                ok += 1
            except LdConsoleError as exc:
                log.warning("还原 %s 失败：%s", i, exc)
        print(f"还原完成：{ok}/{end - start + 1}")

    # ================= 其它 =================

    def create_txt(self):
        data = device.read_config()
        start = data.get("cache_start_id", 126)   # 起始编号
        count = data.get("cache_count", 25)        # 总数
        num = data.get("cache_repeat", 4)          # 每个编号重复次数
        content = ''
        index = 1
        while index <= count:
            name = f'雷电{start}'
            for i in range(num):
                content = content + name + '\n'
            start += 1
            index += 1
        device.write_txt(os.path.join(device.PROJECT_ROOT, 'cache.txt'), content, 'w')

    def default(self):
        print("default")

    def quitall(self):
        """关闭全部模拟器（CLI 专用）。"""
        if not self.use_cli:
            print("quitall 需要 CLI 后端")
            return
        self.ld.quit_all()

    def switch(self, case):
        method = getattr(self, case, self.default)
        return method()
