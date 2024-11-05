from apscheduler.schedulers.background import BackgroundScheduler
import time

def start(fn,second=0, minute=0, hour=0):
    """
        启动定时任务
        :param fn: 任务函数
        :param second: 秒
        :param minute: 分
        :param hour: 时
    """
    # 创建调度器实例
    scheduler = BackgroundScheduler(timezone='Asia/Shanghai')  # 设置时区

    # 添加定时任务
    job = scheduler.add_job(
            fn,
            trigger='cron',
            second=second,
            minute=minute,
            hour=hour, 
    )
    print(job)
    # 启动调度器
    scheduler.start()
    print("Scheduler started.")

    try:
        # 模拟主程序运行
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        # 终止调度器
        job.remove()
        print("Scheduler has been shut down.")