#!/usr/bin/env python3
import re, time, json, random
import subprocess as sp
import requests
import ddddocr
import halo

STATUS = 'NONE'
_ITEM  = dict()
TIMEOUT = 5

ocr = ddddocr.DdddOcr()
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:96.0) Gecko/20100101 Firefox/96.0",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
})
halo_info = halo.Halo()
with open('config.json') as f:
    ACCOUNT_INFO = json.load(f)

def login():
    global STATUS, _ITEM
    halo_info.start()
    halo_info.text = 'Try to login ...'
    #
    login_flag = False
    while not login_flag:
        got_verify_code = False
        while not got_verify_code:
            time.sleep( random.random() )
            _id = random.random()
            try:
                res = session.get( f'https://hk.sz.gov.cn/user/getVerify?{_id}', timeout=TIMEOUT )
            except:
                return
            if res.status_code == 200:
                got_verify_code = True
        #
        verifyCode = ocr.classification( res.content )
        ACCOUNT_INFO.update({ "verifyCode" : verifyCode })
        try:
            res = session.post( 'https://hk.sz.gov.cn/user/login', data=ACCOUNT_INFO, timeout=TIMEOUT )
        except:
            return
        #
        login_flag = (res.json()['status'] == 200)
    #
    halo_info.succeed( 'Login with session: {}.'.format(session.cookies) )
    STATUS = 'LOGIN'

def can_reserve():
    global STATUS, _ITEM
    halo_info.start()
    halo_info.text = 'Checking booking status ...'

    try:
        res = session.post('https://hk.sz.gov.cn/passInfo/userCenterIsCanReserve')
        content = res.json()
    except:
        return
    if content['status'] == 200:
        halo_info.succeed( 'Now can reserve.' )
        STATUS = 'CAN_RESERVE'
    elif content['status'] == 304:
        halo_info.fail( 'Session expired. Try login again.' )
        STATUS = 'NONE'
    elif content['status'] == 500:
        halo_info.text = 'Cannot reserve, waiting ...'
        time.sleep(3)
    else:
        halo_info.fail( f'Unknown status, reset session.' )
        print( content )
        STATUS = 'NONE'
        return

def get_list():
    global STATUS, _ITEM
    halo_info.start()
    halo_info.text = "Checking booking list ..."

    got_slot = False
    _counter = 0
    while not got_slot:
        try:
            res = session.post('https://hk.sz.gov.cn/districtHousenumLog/getList', timeout=TIMEOUT)
        except:
            continue
        #
        if res.status_code == 502:
            halo_info.info( '502 Bad Gateway. Nothing serious.' )
            return
        elif res.status_code == 304:
            halo_info.fail( 'Session expired. Try login again.' )
            STATUS = 'NONE'
            return
        elif res.status_code != 200:
            print( res.status_code, res.text )
            continue
        else:
            try:
                content = res.json()
            except:
                pass
            else:
                for item in content['data'][::-1]:
                    if item['count'] > 0:
                        _ITEM = {
                            'date': item['date'],
                            'timespan': item['timespan'],
                            'sign': item['sign']
                        }
                        _msg = f'Find slot on {item["date"]}, {item["count"]} left.'
                        halo_info.succeed( _msg )
                        sp.run(f'notify-send "{_msg}"', shell=True)
                        got_slot = True
                    pass
        #
        _counter += 1
        halo_info.text = f'No hope, try later ({_counter}) ...'
        time.sleep( 1 + random.random() )
    STATUS = 'GET_LIST'

def confirm_order():
    global STATUS, _ITEM
    halo_info.start()
    halo_info.text = 'TRY TO CONFIRM ORDER!'

    _url = f"https://hk.sz.gov.cn/passInfo/confirmOrder?checkinDate=${_ITEM['date']}&t=${_ITEM['timespan']}&s=${_ITEM['sign']}"
    print(_url)

    try:
        res  = session.get(_url, timeout=TIMEOUT)
    except:
        return
    content = res.json()
    #
    if content['status'] == 500:
        halo_info.fail( 'Booking failed, back to list fetching.' )
        print(content)
        STATUS = 'CAN_RESERVE'
        return
    #
    print('In confirm page:')
    print( res.status_code, res.text )
    #
    halo_info.succeed( 'Enjoy your journey~' )
    print(_ITEM)
    STATUS = 'FINISHED'

if __name__=='__main__':
    STATE_DRIVER = {
        'NONE': login,
        'LOGIN': can_reserve,
        'CAN_RESERVE': get_list,
        'GET_LIST': confirm_order,
    }

    while STATUS!='FINISHED':
        STATE_DRIVER[STATUS]()
    