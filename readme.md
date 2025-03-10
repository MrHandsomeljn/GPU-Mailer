# GPU服务器显存监控/邮件提醒

用ai写的一个简单的GPU服务器监控小程序

适合多人合用GPU服务器，时常需要抢资源的场景

使用QQ邮箱，能直接推送到微信上

## 实现逻辑

- 设定显卡显存阈值（如500M），低于阈值算空闲显卡
- 设定显卡空闲时长（如30s），区分是否为长期空闲显卡
- 每5s
  - 从gpustat里获取各个显卡的使用情况报告
  - 对比上一次获取的报告情况，输出到终端
  - 对于当前空闲显卡，若显卡空闲满足30s，记录为长期空闲显卡
  - 对于非空闲显卡，刷新记录为非空闲显卡
  - 若无本人进程在线，且长期空闲显卡有无状态发生变化，则发送邮件

## 实现效果
<img src="img/demo.jpg" style="width:50%"></img>
<img src="img/demo2.jpg" style="width:50%"></img>

## get start
1. `git clone git@github.com:MrHandsomeljn/GPU-Mailer.git`
2. `cd gpu_mailer`
3. `pip install gpustat`
4. `mv gpu_mailer_config_template.py gpu_mailer_config.py`，在`gpu_mailer_config.py`文件写入个人信息
5. 开一个tmux或者守护进程（保证终端下线后还能提醒）
6. `python gpu_mailer.py`