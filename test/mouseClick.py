import pyautogui
import pyperclip
import cv2
pyautogui.FAILSAFE = True # 禁用安全退出


def auto_click(x,y):
    pyautogui.click(x, y)

def get_xy(img_path):
    """
    获取图片在屏幕上的位置
    :param img_path: 图片路径
    :return: 以元组的形式返回检测到的区域的中心坐标
    """

    # 将屏幕截图保存
    pyautogui.screenshot('image/screenshot.png')
    # 载入截图
    screenshot = cv2.imread('image/screenshot.png')
    # 载入模板图片
    template = cv2.imread(img_path)
    # 读取模板图片的宽高
    height, width = template.shape[:2]
    # 在截图中进行模板匹配
    result = cv2.matchTemplate(screenshot, template, cv2.TM_SQDIFF_NORMED)
    # 解析出匹配区域的左上角坐标
    top_left = cv2.minMaxLoc(result)[2]
    # 计算匹配区域右下角坐标
    bottom_right = (top_left[0] + width, top_left[1] + height)
    # 计算出匹配区域的中心坐标
    center = (int((top_left[0] + bottom_right[0]) / 2), int((top_left[1] + bottom_right[1]) / 2))
    return center


def main():
    # pyautogui.click(x, y) # 鼠标点击
    # pyautogui.sleep(3) # 等待3秒
    # pyautogui.keyDown('ctrl') # 按下ctrl键
    # pyautogui.keyUp('ctrl') # 释放ctrl键
    # pyautogui.press('enter') # 点击enter键
    # pyautogui.typewrite('Hello, world!') # 输入文本
    # pyautogui.hotkey('ctrl', 'c') # 模拟ctrl+c快捷键
    # pyautogui.screenshot('screenshot.png') # 截屏并保存为screenshot.png
    # pyautogui.moveTo(100, 100) # 移动鼠标到(100, 100)位置
    # pyautogui.moveRel(100, 100) # 相对当前位置移动鼠标到(100, 100)位置
    # pyautogui.dragTo(200, 200, duration=1) # 拖动鼠标到(200, 200)位置，持续1秒
    # pyautogui.scroll(10) # 向上滚动10个单位
    # pyautogui.mouseDown() # 按下鼠标左键
    # pyautogui.mouseUp() # 释放鼠标左键
    # pyautogui.mouseDown(button='left') # 按下鼠标左键
    # pyautogui.mouseUp(button='left') # 释放鼠标左键
    # pyautogui.mouseDown(button='right') # 按下鼠标右键
    # pyautogui.mouseUp(button='right') # 释放鼠标右键
    # pyautogui.mouseDown(button='middle') # 按下鼠标中键
    # pyautogui.mouseUp(button='middle') # 释放鼠标中键


    # x,y= pyautogui.position() # 获取当前鼠标位置
    # print(x,y)
    # pyautogui.moveRel(100, 100)
    # position= pyautogui.position() # 获取当前鼠标位置
    # print(position)
    # width,height= pyautogui.size() # 获取屏幕分辨率
    # print(width,height)
    # onscreen= pyautogui.onScreen(x,y) # 判断当前鼠标位置是否在屏幕范围内
    # print(onscreen)

    # 拖动窗口：右上角文件拖动到屏幕左上角
    pyautogui.mouseDown(1865, 35, button='left') # 按下鼠标右键
    # 移动鼠标到目标位置
    pyautogui.moveTo(35,35,duration=3)  # duration 参数控制移动速度
    # 释放左键完成拖动
    pyautogui.mouseUp()
    print('窗口已移动到屏幕左上角')

    # 复制粘贴文本
    # pyperclip.copy('你好，世界！')
    # pyautogui.click(478,644)
    # pyautogui.hotkey('ctrl','v')

    # 人机交互对话框
    # pyautogui.alert('你好，世界！')
    # result = pyautogui.alert(title='标题',text='内容',button='关闭')
    # print(result)

    # result = pyautogui.confirm(title='标题',text='内容',buttons=['OK','Cancel'])
    # print(result)

    # result = pyautogui.prompt(title='标题',text='内容',default='默认值')
    # print(result)

    # result = pyautogui.password(title='标题',text='内容',default='默认密码',mask='*')
    # print(result)

    # 截图
    # pyautogui.screenshot().save('image/screenshot.png')

    # 截取指定区域
    # screenshot = pyautogui.screenshot(region=(0,0,800,600)) # (x,y,w,h)
    # screenshot.save('image/screenshot.png')
    # location = pyautogui.locateOnScreen('image/1.png')
    # print('location:',location)

    # location2 = pyautogui.locateOnScreen('image/2.png',confidence=0.7,grayscale=True) # confidence:相似度，grayscale:灰度
    # print('location2',location2)

    # location3 = get_xy('image/2.png')
    # print('location3',location3)




if __name__ == "__main__":
    main()






















