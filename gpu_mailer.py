import time
import gpustat
import smtplib
import subprocess
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from gpu_mailer_config import user, pswd, threshold_MB, duration_sec, interval_sce, server, port, server_user_name

def get_gpu_count():
    gpus = gpustat.GPUStatCollection.new_query()
    return len(gpus)

gpu_count = get_gpu_count()

def dicts_different_to_str(dict1, dict2):
    differences = {}

    # 检查dict1中的键
    for key in dict1:
        if key not in dict2:
            differences[key] = f"Del {dict1[key]}"
        elif dict1[key] != dict2[key]:
            differences[key] = f"modified \n    {dict1[key]}\n -> {dict2[key]}"

    # 检查dict2中的键
    for key in dict2:
        if key not in dict1:
            differences[key] = f"Add {dict2[key]}"

    diff_strs = []
    if differences:
        print(fr'【{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}】')
        for key, change in differences.items():
            diff_str = f"GPU {key} : {change}"
            diff_strs.append(diff_str)
            print(diff_str)
        print()
    return diff_strs

def email_send(recv, head, content):
    # 邮件配置信息
    smtp_server = server  # 邮箱服务器
    smtp_port = port  # 邮箱端口
    smtp_ssl = True  # 启用ssl
    smtp_user = user
    smtp_password = pswd  # 邮箱授权码，到邮箱网站中查看
 
    # 发送邮件信息
    sender = user  # 发送者邮箱
    receivers = [recv]  # 接收者邮箱
 
    # 邮件正文
    message = MIMEText(content, 'plain', 'utf-8')  # 邮件正文格式
 
    # 邮件信息配置
    message['From'] = user  # 邮件标头中发件人，不影响实际发送邮箱
    message['To'] = recv  # 邮件标头中收件人，不影响实际送达邮箱
    message['Subject'] = Header(head, 'utf-8')  # 邮件标题
 
    # 发送邮件
    try:
        smtp_obj = smtplib.SMTP_SSL(smtp_server, smtp_port)  # 连接服务器
        smtp_obj.login(smtp_user, smtp_password)  # 登入发送者邮箱
        smtp_obj.sendmail(sender, receivers, message.as_string())  # 发送邮件指令
        print(f"邮件发送成功: {sender} -> {receivers}")
 
    except smtplib.SMTPException as e:
        print("Error: 邮件发送失败: ", e)

def func(title, message):
    email_send(user, title, message)

def get_gpu_processes():
    """获取每个GPU上运行的进程信息"""
    gpu_processes = {}
    try:
        # 使用gpustat库获取GPU进程信息
        gpus = gpustat.GPUStatCollection.new_query()
        
        for gpu in gpus:
            gpu_id = gpu.index  # GPU ID
            memory_used = gpu.memory_used  # 当前显存使用
            processes = gpu.processes  # 当前GPU上运行的进程信息

            if gpu_id not in gpu_processes:
                gpu_processes[gpu_id] = {
                    'memory_used_MB': memory_used,
                    'processes': []
                }

            for process in processes:
                user = process['username']
                pid = process['pid']
                mem = process['gpu_memory_usage']  # 使用gpustat提供的内存信息
                if user == "gdm": continue
                gpu_processes[gpu_id]['processes'].append({
                    'user': user,
                    'pid': pid,
                    'memory_used_MB': mem
                })

    except Exception as e:
        print("获取GPU进程信息失败:", e.with_traceback())
    return gpu_processes


# state：空闲GPU的个数
# state>0 发一封
# state=0 发一封
# 在线时不发
def monitor_gpu_memory(threshold_MB=100, duration_sec=1):
    last_state_count = 0 # 假设一开始没空GPU
    gpu_free_time = {}
    last_gpu_info = {}
    gpu_free_for_duration = [False] * gpu_count # 假设一开始都是空GPU
    while True:
        online = False
        
        gpu_processes = get_gpu_processes()  # 获取GPU上运行的进程

        for gpu_id, info in gpu_processes.items():
            online = online or any([process['user']==server_user_name for process in info['processes']])

            memory_used = info['memory_used_MB']

            if memory_used < threshold_MB:
                now = time.time()
                if gpu_id not in gpu_free_time:
                    gpu_free_time[gpu_id] = now
                    gpu_free_for_duration[gpu_id] = False
                elif now - gpu_free_time[gpu_id] >= duration_sec:
                    gpu_free_for_duration[gpu_id] = True
            else:
                gpu_free_for_duration[gpu_id] = False
                gpu_free_time.pop(gpu_id, None)
        
        diff = dicts_different_to_str(last_gpu_info, gpu_processes)
        last_gpu_info = gpu_processes

        if not online:
            title = ""
            free_gpu = [str(index) for index, value in enumerate(gpu_free_for_duration) if value]
            if last_state_count == 0 and free_gpu       : title = f"【GPU空闲】{','.join(free_gpu)}"
            if last_state_count > 0  and free_gpu == [] : title = f"【GPU已满】"
            
            if title:
                message1 = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n"
                message2 = '\n'.join(diff)
                message3 = ""
                processes = info['processes']  # 当前GPU上运行的进程信息
                message3 += f"GPU {gpu_id}: {memory_used} MB\n"
                for process in processes:
                    message3 += f"  User: {process['user']}, PID: {process['pid']}, Memory Used: {process['memory_used_MB']} MB\n"

                message = message1 + message2 + message3
                func(title, message)
                gpu_free_time.clear()

        time.sleep(interval_sce)

if __name__ == "__main__":
    monitor_gpu_memory(threshold_MB, duration_sec)
