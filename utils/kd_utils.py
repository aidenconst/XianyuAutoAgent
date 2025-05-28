# API查询
import requests
import os

async def query_express_fee(str_data, post_url):
    try:
        # 解析输入字符串
        parts = str_data.split('-')
        if len(parts) < 5:
            return None
            
        # 提取省份城市和重量
        sender_province, sender_city, receive_province, receive_city, weight_part = parts
        weight = int(weight_part.replace('kg', '').strip())  # 去除kg并转为整数
        # 读取authorization值
        authorization = os.getenv("AUTUORIZATION")
        # 构建请求数据
        json_data = {
            "customerType": "kd",
            "payMethod": 30,
            "goods": "普货",
            "weight": weight,
            "packageCount": 1,
            "senderProvince": sender_province,
            "senderCity": sender_city,
            "receiveProvince": receive_province,
            "receiveCity": receive_city
        }

        # 设置请求头
        headers = {
            'Authorization': authorization,
            'Content-Type': 'application/json',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        }

        # 发送POST请求
        response = requests.post(post_url, json=json_data, headers=headers)
        response.raise_for_status()  # 检查请求是否成功

        # 处理响应数据
        data = response.json()
        y_list = data.get('data', {}).get('Y', [])

        # 按preOrderFee排序
        sorted_y = sorted(y_list, key=lambda x: float(x['preOrderFee']))

        # 计算text和info字段
        text_values = f"{sorted_y[0]['channelName']}:{float(sorted_y[0]['preOrderFee']) - float(sorted_y[0]['couponAmount'])}"
        info_lines = []
        for item in sorted_y:
            pre_order_fee = float(item['preOrderFee'])
            coupon_amount = float(item['couponAmount']) if item['couponAmount'] else 0.0
            text_value = pre_order_fee - coupon_amount
            #text_values.append(round(text_value, 2))  # 保留两位小数
                
            # 构建info字符串
            info_line = f"{item['channelName']}：{text_value:.2f}--{item['price']}"
            info_lines.append(info_line)

        return {
            'channelInfo':f"{sender_province}-{sender_city} 寄 {receive_province}-{receive_city} - [{weight}kg]\n",
            'text': text_values,#最便宜快递
            'info': '\n\n'.join(info_lines) #所有快递
        }
    except Exception:
        return False