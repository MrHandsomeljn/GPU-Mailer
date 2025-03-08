import smtplib  # 邮件发送模块
from email.mime.text import MIMEText
from email.header import Header
import time
import subprocess
from datetime import datetime

from gpu_mailer_config import user, pswd, threshold_MB, duration_sec, interval_sce, server, port, max_gpu_count


def compare_dicts(dict1, dict2):
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

def func(message):
    email_send(user, "【GPU空置】", message)

def get_gpu_processes():
    """获取每个GPU上运行的进程信息"""
    gpu_processes = {}
    try:
        # 调用gpustat命令获取GPU进程信息
        output = subprocess.check_output(['gpustat', '--no-color', '-c', '-u', '-p', '-F'], stderr=subprocess.STDOUT)
        output_lines = output.decode('utf-8').strip().split('\n')

        for line in output_lines[1:]:  # 跳过第一行
            parts = line.split('|')
            gpu_id = int(parts[0][1])  # GPU ID
            memory_used = int(parts[2].split('/')[0])  # 当前显存使用
            processes = parts[3].strip().split() if len(parts) > 1 else []

            if gpu_id not in gpu_processes:
                gpu_processes[gpu_id] = {
                    'memory_used_MB': memory_used,
                    'processes': []
                }

            for process in processes:
                process = process.strip()
                process = process.split(":")
                user = process[0]
                process = process[1].split("/")
                pname = process[0]
                process = process[1].split("(")
                pid = process[0]
                mem = process[1][:-2]
                if user == "gdm": continue
                gpu_processes[gpu_id]['processes'].append({
                    'user': user,
                    'pid': pid,
                    'memory_used_MB': mem
                })

    except subprocess.CalledProcessError as e:
        print("获取GPU进程信息失败:", e.with_traceback())  # 输出错误信息
    except Exception as e:
        print("获取GPU进程信息失败:", e.with_traceback())
    return gpu_processes


def monitor_gpu_memory(threshold_MB=100, duration_sec=1):
    low_memory_gpus = {}
    func_used = [True] * max_gpu_count
    last_gpu_info = {}
    message = ""
    while True:
        gpu_processes = get_gpu_processes()  # 获取GPU上运行的进程
        need_func = False

        for gpu_id, info in gpu_processes.items():
            memory_used = info['memory_used_MB']  # 当前GPU的显存占用
            processes = info['processes']  # 当前GPU上运行的进程信息
            message += f"GPU {gpu_id}: {memory_used} MB\n"
            for process in processes:
                message += f"  User: {process['user']}, PID: {process['pid']}, Memory Used: {process['memory_used_MB']} MB\n"

            # 检查显存占用是否低于阈值
            if memory_used < threshold_MB:
                if gpu_id not in low_memory_gpus:
                    low_memory_gpus[gpu_id] = time.time()  # 记录时间
                elif time.time() - low_memory_gpus[gpu_id] >= duration_sec:
                    if func_used[gpu_id] == False:
                        func_used[gpu_id] = True
                        need_func = True  # 达到持续时间，标记需要调用func
            else:
                if gpu_id in low_memory_gpus:
                    del low_memory_gpus[gpu_id]  # 重置状态
                    func_used[gpu_id] = False
        diff = compare_dicts(last_gpu_info, gpu_processes)
        last_gpu_info = gpu_processes

        # 有我的进程，就不发邮件（在线状态）
        if need_func:
            for gpu_id, info in gpu_processes.items():
                for process in processes:
                    if process['user'] == "ljn": need_func = False

        if need_func:
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n"
            message = date+'\n'+'\n'.join(diff)+'\n'+message
            func(message)
            low_memory_gpus.clear()

        time.sleep(interval_sce)

if __name__ == "__main__":
    monitor_gpu_memory(threshold_MB, duration_sec)
