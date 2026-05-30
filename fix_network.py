#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断并修复网络连接问题"""
import os
import sys

# 1. 清除所有可能的代理设置
proxy_keys = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 
              'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']
for key in proxy_keys:
    val = os.environ.pop(key, None)
    if val:
        print(f"已清除代理: {key}={val}")

# 2. 检查注册表中的代理设置（Windows）
if sys.platform == 'win32':
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                             r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
        proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0] if proxy_enable else "disabled"
        print(f"\nWindows系统代理: {'启用' if proxy_enable else '禁用'}")
        if proxy_enable:
            print(f"代理服务器: {proxy_server}")
            print(f"\n⚠️ 检测到Windows系统代理已启用！这可能是导致连接问题的原因。")
            print(f"\n请手动操作：")
            print(f"  1. 打开 设置 > 网络和Internet > 代理")
            print(f"  2. 关闭 '使用代理服务器'")
            print(f"  3. 或者在Internet选项中关闭代理")
            print(f"\n或者运行以下命令关闭代理：")
            print(f'  reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f')
        else:
            print("系统代理已禁用")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"无法读取注册表: {e}")

# 3. 测试直连
import requests
print("\n" + "="*60)
print("测试直连（绕过代理）...")

# 方法1: 直接requests.get
try:
    r = requests.get("http://push2his.eastmoney.com/api/qt/stock/kline/get",
                      params={"fields1":"f1,f2,f3,f4,f5,f6",
                              "fields2":"f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
                              "ut":"7eea3edcaed734bea9cbfc24409ed989",
                              "klt":"101","fqt":"1",
                              "secid":"1.600519","beg":"20260101","end":"20260530"},
                      timeout=15)
    if r.status_code == 200:
        data = r.json()
        klines = data.get('data', {}).get('klines', [])
        print(f"✅ 直连成功! 获取 {len(klines)} 条K线")
    else:
        print(f"❌ HTTP状态码: {r.status_code}")
except Exception as e:
    print(f"❌ 直连失败: {e}")

# 方法2: 使用socket直接连接
print("\n测试socket直连...")
import socket
try:
    sock = socket.create_connection(("push2his.eastmoney.com", 80), timeout=10)
    sock.sendall(b"GET /api/qt/stock/kline/get?secid=1.600519&klt=101&fqt=1&beg=20260101&end=20260530&fields1=f1&fields2=f51,f52,f53,f54,f55,f56 HTTP/1.1\r\nHost: push2his.eastmoney.com\r\n\r\n")
    response = sock.recv(4096).decode('utf-8', errors='ignore')
    sock.close()
    if '200' in response[:50]:
        print(f"✅ Socket直连成功! 响应长度: {len(response)}")
    else:
        print(f"❌ Socket响应: {response[:200]}")
except Exception as e:
    print(f"❌ Socket直连失败: {e}")

# 方法3: 使用urllib
print("\n测试urllib直连...")
import urllib.request
try:
    url = "http://push2his.eastmoney.com/api/qt/stock/kline/get?fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116&ut=7eea3edcaed734bea9cbfc24409ed989&klt=101&fqt=1&secid=1.600519&beg=20260101&end=20260530"
    # 创建不使用代理的opener
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    response = opener.open(url, timeout=15)
    content = response.read().decode('utf-8')
    print(f"✅ urllib直连成功! 内容长度: {len(content)}")
except Exception as e:
    print(f"❌ urllib直连失败: {e}")

print("\n" + "="*60)
print("如果所有方法都失败，请检查：")
print("  1. Windows防火墙是否阻止了Python")
print("  2. 杀毒软件是否阻止了网络访问")
print("  3. 运行CMD: netsh winsock reset 然后重启电脑")
print("  4. 检查 hosts 文件是否被修改")