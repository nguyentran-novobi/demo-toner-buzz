# -*- coding: utf-8 -*-

def _standardize_vals(env, model, datas):
    try:
        vals = datas.copy()
        for key in list(datas.keys()):
            if key not in env[model]._fields:
                del vals[key]
        return vals
    except Exception as e:
        return datas
