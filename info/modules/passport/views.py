import random
import re

from flask import request, abort, current_app, make_response, jsonify
from werkzeug.wrappers import json

from info import redis_store, constants
from info.libs.yuntongxun.sms import CCP
from info.utils.response_code import RET
from . import passport_blu
from info.utils.captcha.captcha import captcha


@passport_blu.route('/smscode',methods=["POST"])
def send_sms():
    # params_dict=json.loads(request.data)
    params_dict=request.json
    mobile = params_dict.get("mobile")
    image_code = params_dict.get("image_code")
    image_code_id = params_dict.get("image_code_id")

    if not all([mobile, image_code_id, image_code]):
        # 参数不全
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")

    if not re.match("^1[3578][0-9]{9}$", mobile):
        # 提示手机号不正确
        return jsonify(errno=RET.PARAMERR, errmsg="手机号不正确")

    try:
        real_image_code = redis_store.get("ImageCode_" + image_code_id)
    except Exception as e:
        current_app.logger.error(e)
        # 获取图片验证码失败
        return jsonify(errno=RET.DBERR, errmsg="获取图片验证码失败")

    if not real_image_code:
        # 验证码已过期
        return jsonify(errno=RET.NODATA, errmsg="验证码已过期")

    if image_code.lower() != real_image_code.lower():
        # 验证码输入错误
        return jsonify(errno=RET.DATAERR, errmsg="验证码输入错误")


    sms_code_str="%06d" % random.randint(0,999999)
    current_app.logger.debug("短信验证码内容是：%s" % sms_code_str)
    result = CCP().send_template_sms(mobile, [sms_code_str, constants.SMS_CODE_REDIS_EXPIRES / 60], "1")
    if result !=0:
        # 发送短信失败
        return jsonify(errno=RET.THIRDERR, errmsg="发送短信失败")

    try:
        redis_store.set("SMS_" + mobile, sms_code_str, constants.SMS_CODE_REDIS_EXPIRES)
    except Exception as e:
        current_app.logger.error(e)
        # 保存短信验证码失败
        return jsonify(errno=RET.DBERR, errmsg="保存短信验证码失败")

        # 7. 返回发送成功的响应
    return jsonify(errno=RET.OK, errmsg="发送成功")



@passport_blu.route('/image_code')
def get_image_code():
    image_code_id=request.args.get('imageCodeId',None)
    if not image_code_id:
        return abort(403)

    name,text,image=captcha.generate_captcha()

    try:
        redis_store.set('ImageCodeId_'+image_code_id,text,constants.IMAGE_CODE_REDIS_EXPIRES)
    except Exception as e:
        current_app.logger.error(e)
        abort(500)
    response=make_response(image)
    response.headers['Content-Type']="image/jpg"
    return response
