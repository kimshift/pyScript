# -*- coding: utf-8 -*-
"""WorkBuddy 积分任务 —— 命令行入口。

用法：
    python -m tools.wb_reward                 # 默认 all（签到 + 旅行）
    python -m tools.wb_reward checkin         # 只签到
    python -m tools.wb_reward travel          # 只旅行
    python -m tools.wb_reward growth auto     # 成长计划（有可领才领）
    python -m tools.wb_reward health          # token 有效期 + 只读探活
    python -m tools.wb_reward status          # 只读探活

    mise run wb:all / wb:checkin / wb:travel / wb:growth / wb:health / wb:status

退出码：0 成功｜1 业务失败｜2 环境缺失｜3 超时｜4 IO｜5 已有实例在跑（跳过）
"""

import sys

from tools.wb_reward.runner import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
