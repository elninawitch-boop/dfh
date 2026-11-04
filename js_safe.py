# -*- coding: utf-8 -*-
"""安全的 JS 调用：用 base64 传参，避免任何编码/转义问题"""
import base64
import json


def js_safe(view, func, obj):
    """调用 JS 函数并安全传参

    把 JSON 转成 base64，JS 端 decode 后 parse，
    彻底避免中文、引号、反斜杠导致的语法错误。
    """
    if obj is None:
        code = "if(window.%s) window.%s(null);" % (func, func)
    else:
        payload = json.dumps(obj, ensure_ascii=False)
        b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        code = (
            "if(window.%s){"
            "  try{"
            "    var raw = atob('%s');"
            "    var bytes = new Uint8Array(raw.length);"
            "    for(var i=0;i<raw.length;i++) bytes[i]=raw.charCodeAt(i);"
            "    var txt = new TextDecoder('utf-8').decode(bytes);"
            "    window.%s(JSON.parse(txt));"
            "  }catch(e){ console.error('[js_safe]', e); }"
            "}" % (func, b64, func)
        )
    view.page().runJavaScript(code)
