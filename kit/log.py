# -*- coding: utf-8 -*-
"""统一日志：新脚本用 get_logger()，不要再散落 print。

用法：
    from kit.log import get_logger
    log = get_logger(__name__)
    log.info("开始处理 %s", name)
    log.exception("失败了")   # 自动带堆栈

级别可用环境变量覆盖：LOG_LEVEL=DEBUG
"""

import logging
import os
import sys

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    """返回配置好的 logger（重复调用不会重复加 handler）。"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO))
    logger.propagate = False
    return logger
