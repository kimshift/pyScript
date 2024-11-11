# 字典文件

# 雷电模拟器
emulator = {
    '排列窗口': 'win',
    '搜索': 'search',
    '下拉': 'select',
    '图标': 'logo',
    '全选': 'check_all',
    '备份/还原': 'mirror',
    '备份': 'backup',
    '还原': 'restore',
    '批量启动': 'batch_start',
    '批量新增': 'batch_create',
    '批量删除': 'batch_delete',
    '批量设置': 'batch_setting',
    '批量操作': 'batch_operation',
    '其他设置': 'order_setting',
    '分辨率': 'ratio',
    '内存': 'storage',
    '退出选项': 'quit_op',
    '保存设置': 'save_setting',
    '确定': 'ok',
    '启动': 'start',
    '不在提示': 'none_tip',
    '不谢谢': 'no_thanks',
    '雷电选项': 'ld_op',
    '同步选项': 'async_op',
    '开启同步': 'open_async',
    '关闭同步': 'close_async',
    '关闭同步窗口': 'close_async_win',
    '最小化雷电多开': 'mini_ld_dk',
    '关闭雷电多开': 'close_ld_dk',
    'APK选项': 'apk_op',
    '选择APK': 'select_apk',
    '支付宝app': 'ant_app',
    '支付宝权限': 'ant_auth',
    '存储空间':'storage_space',
    '电话':'phone',
    '麦克风':'microphone',
    '通讯录':'address_book',
    '位置信息':'location_info',
    '相机':'camera',
}

common = {
    '文件保存': 'file_save',
    '文件取消': 'file_cancel',
    '路径搜索': 'path_search', 
    '文件搜索': 'file_search', 
    '文件打开': 'file_open', 
    '关闭支付宝文件夹': 'close_ant_file', 
    '最小化vscode': 'mini_vscode', 
}


left_btn = ['全选']
right_btn = [
        '最小化vscode','关闭vscode','关闭同步窗口','最小化雷电多开',
        '关闭雷电多开'
    ]

dict = {
    'emulator': emulator,
    'common': common,
    'left_btn': left_btn,
    'right_btn': right_btn,
    'global': { **emulator, **common}
}

