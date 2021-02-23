#!/usr/bin/env python3
import json
import logging
import re
import socket
import sys
from io import BytesIO
from optparse import OptionParser
from time import sleep

import requests

import config


logger = logging.getLogger("main")
logger.setLevel('INFO')
formatter = logging.Formatter("%(asctime)s - [%(levelname)s]: %(message)s")
chlr = logging.StreamHandler()
chlr.setFormatter(formatter)
logger.addHandler(chlr)


class check_server:
    """
    该类主要是利用socket建立一个连接以后，发送一个http请求，然后根据返回的状态码，判断主机的健康状况
    """

    def __init__(self, address, port, resource, timeout):
        self.__address = address
        self.__port = port
        self.__resource = resource
        if timeout <= 0:
            timeout = 1
        self.__timeout = timeout

    def check(self):
        """
        该方法也是该类的主要方法，包括构建请求资源，解析返回结果等
        """
        if not self.__resource.startswith('/'):
            self.__resource = '/' + self.__resource

        request = "GET %s HTTP/1.1\r\nHost:%s\r\n\r\n" % (self.__resource, self.__address)

        s = socket.socket()
        s.settimeout(self.__timeout)

        try:
            s.connect((self.__address, self.__port))
            s.send(request.encode())
            response = s.recv(100)
        except socket.error as e:
            logger.debug("连接%s 上端口 %s 失败 ,原因为:%s" % (self.__address, self.__port, e))
            return False
        finally:
            s.close()

        line = BytesIO(response).readline()

        try:
            (http_version, status, messages) = re.split(r'\s+', line.decode(), 2)
        except ValueError:
            logger.warning("分割响应码失败")
            return False
        if status in ['200', '301', '302']:
            return True
        else:
            return False


def send_text_message(message):
    resp = requests.post("https://sms-api.luosimao.com/v1/send.json",
                         auth=("api", "key-" + config.Luosimao_Apikey),
                         data={
                             "mobile": config.phone_number,
                             "message": "%s【%s】" % (message, config.message_sign)
                         }, timeout=3)
    result = json.loads(resp.content)
    logger.debug(result)


if __name__ == '__main__':
    """
    处理参数
    """
    parser = OptionParser()
    parser.add_option("-a", "--address", dest="address", default='127.0.0.1', help="要检查主机的地址")
    parser.add_option('-p', '--port', dest="port", type=int, default=80, help="要检查主机的端口")
    parser.add_option('-r', '--resource', dest="resource", default="/", help="要检查的资源，比如/")
    parser.add_option('-t', '--tiem-out', dest="timeout", type=int, default=1, help="连接超时时间(s)")
    parser.add_option('-c', '--confirm-time', dest="confirm_time", type=int, default=10, help="推送改变所需的状态连续改变的次数")
    parser.add_option('-d', '--confirm-delay', dest="confirm_delay", type=int, default=6, help="监控状态的时间间隔(s)")
    parser.add_option('-n', '--name', dest="name", default=config.default_device_name, help="推送中显示的设备名称")
    (options, args) = parser.parse_args()

# 开始检测
checks = check_server(options.address, options.port, options.resource, options.timeout)

status = checks.check()
while True:
    check_res = checks.check()
    logger.info(check_res)
    if check_res != status:
        for i in range(1, options.confirm_time + 1):
            sleep(options.confirm_delay)
            check_res = checks.check()
            logger.info(check_res)
            if check_res == status:
                break
        if i == options.confirm_time:
            if status == True:  # 设备离线
                logger.info("设备离线")
                send_text_message("您的设备 [%s:%s](%s） 已离线，请注意" % (options.address, options.port, options.name))
                status = False
            else:  # 设备上线
                logger.info("设备上线")
                send_text_message("您的设备 [%s:%s](%s） 已上线，请注意" % (options.address, options.port, options.name))
                status = True
    sleep(options.confirm_delay)
