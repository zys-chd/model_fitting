import tkinter as tk

# 创建主窗口
window = tk.Tk()
window.title("我的应用程序")

# 设置图标
window.iconbitmap("model_fitting.ico")

# 修改任务栏图标
window.iconphoto(True, tk.PhotoImage(file='model_fitting.png'))
window.wm_iconphoto(True, tk.PhotoImage(file='model_fitting.png'))

window.mainloop()