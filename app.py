# -*- coding: utf-8 -*-
"""
Otomasyon Dashboard — Flask ana uygulaması.
Çalıştırma:  python app.py   ->  http://localhost:5000
"""

import re
from datetime import timedelta
from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for

import config
from modules import opera_module, iccid_module, mdm_es_module, db_helper, auth_module, update_module

app = Flask(__name__)
app.secret_key = config.get_secret_key()
app.permanent_session_lifetime = timedelta(days=3650)  # Sınırsız / 10 yıl oturum süresi
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.json.ensure_ascii = False  # Türkçe karakterler JSON'da düzgün görünsün


@app.context_processor
def inject_user():
    return {'current_user': session.get('user') or {}}


@app.before_request
def require_login():
    # Statik dosyalar ve oturum rotaları doğrulamadan muaftır
    if request.path.startswith('/static/') or request.path in ['/login', '/api/login']:
        return None

    user = session.get('user')
    if not user:
        # Eğer kullanıcı daha önce çıkış yapmamışsa ve yerel yapılandırmada kayıtlıysa oturumu geri yükle
        if not session.get('logged_out'):
            saved_creds = config.get_user_credentials()
            if saved_creds.get('sicil') and saved_creds.get('name'):
                session.permanent = True
                session['user'] = {
                    'user': saved_creds['sicil'],
                    'name': saved_creds['name']
                }
                return None

        if request.path.startswith('/api/'):
            return fail('Oturum açmanız gerekmektedir.', 401)
        return redirect(url_for('login_page', next=request.path))


def ok(data=None, **extra):
    return jsonify({'success': True, 'data': data, **extra})


def fail(error, code=400):
    return jsonify({'success': False, 'error': error}), code


def body():
    return request.get_json(silent=True) or {}


def _get_tp_users_view():
    import ICCID as ICCID_Func
    return [
        {
            'id': uid,
            'name': u['Name'],
            'user': u['User'],
            'has_credentials': bool(u.get('User') and u.get('Password')),
        }
        for uid, u in ICCID_Func.load_users().items()
    ]


# ----------------------------- Oturum / Kimlik Doğrulama -----------------------------

@app.route('/login')
def login_page():
    if session.get('user'):
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    session['logged_out'] = True
    return redirect(url_for('login_page'))


@app.route('/api/login', methods=['POST'])
def api_login():
    d = body()
    username = str(d.get('username', '')).strip()
    password = str(d.get('password', '')).strip()

    if not username or not password:
        return fail('Sicil / Domain ID ve Şifre zorunludur.')

    # TestPortal üzerinden doğrula
    res = auth_module.authenticate_testportal(username, password)
    if not res.get('success'):
        return fail(res.get('error', 'Giriş başarısız. Lütfen bilgilerinizi kontrol ediniz.'))

    # Oturumu başlat
    full_name = res.get('name') or username
    session.permanent = True
    session.pop('logged_out', None)
    session['user'] = {
        'user': username,
        'name': full_name
    }

    # Sicil, şifre ve tam ismi yerel yapılandırmaya kalıcı olarak kaydet
    config.save_user_session_credentials(username, password, full_name)

    return ok({'name': full_name, 'user': username}, message='Giriş başarılı.')


# ----------------------------- Sayfalar -----------------------------

@app.route('/')
def index():
    return render_template('index.html', active_page='home')


@app.route('/opera')
def opera():
    clean_lines = [
        item for item in iccid_module.load_cached_lines()
        if item.get('status') == 'clean' and item.get('iccid')
    ]
    local_cfg = config.load_local_config()
    default_opera_user = local_cfg.get('default_opera_user', '61044774')
    return render_template(
        'opera.html',
        active_page='opera',
        iccid_list=[item.get('iccid') for item in clean_lines],
        test_lines=clean_lines,
        test_customers=getattr(config, 'TEST_CUSTOMERS', []),
        opera_users=getattr(config, 'OPERA_USERS', {}),
        default_opera_user=default_opera_user,
    )


@app.route('/iccid')
def iccid():
    return render_template(
        'iccid.html',
        active_page='iccid',
        test_lines=iccid_module.load_cached_lines(),
        tp_users=_get_tp_users_view(),
    )


@app.route('/testportal-users')
def testportal_users():
    return render_template(
        'testportal_users.html',
        active_page='tp_users',
        tp_users=_get_tp_users_view(),
    )


@app.route('/mdm-es')
def mdm_es():
    return render_template(
        'mdm_es.html',
        active_page='mdm',
        lines=iccid_module.load_cached_lines(),
    )


@app.route('/settings')
def settings_page():
    local_cfg = config.load_local_config()
    shared_cfg = {
        'bscs_dsn': config.BSCS_DB.get('dsn', ''),
        'cmpdb_dsn': config.CMPDB_DB.get('dsn', ''),
        'merns_dsn': config.MERNS_DB.get('dsn', ''),
        'ssh': config.SSH_CONFIG,
        'urls': config.URLS,
        'mdm_es_user': config.MDM_ES.get('user', 'superadmin'),
        'mdm_es_pass': config.MDM_ES.get('password', 'superadmin'),
    }
    return render_template(
        'settings.html',
        active_page='settings',
        local_cfg=local_cfg,
        shared_cfg=shared_cfg,
        opera_users=getattr(config, 'OPERA_USERS', {}),
    )


@app.route('/api/settings/save', methods=['POST'])
def api_settings_save():
    d = body()
    if not isinstance(d, dict):
        return fail('Geçersiz veri formatı.')

    current_cfg = config.load_local_config()

    # DB güncelle
    if 'db' in d and isinstance(d['db'], dict):
        current_cfg.setdefault('db', {})
        for svc in ['bscs', 'cmpdb', 'merns']:
            if svc in d['db'] and isinstance(d['db'][svc], dict):
                current_cfg['db'].setdefault(svc, {})
                current_cfg['db'][svc]['username'] = str(d['db'][svc].get('username', '')).strip()
                current_cfg['db'][svc]['password'] = str(d['db'][svc].get('password', '')).strip()

    # TestPortal güncelle
    if 'testportal' in d and isinstance(d['testportal'], dict):
        current_cfg.setdefault('testportal', {})
        current_cfg['testportal']['user'] = str(d['testportal'].get('user', '')).strip()
        current_cfg['testportal']['password'] = str(d['testportal'].get('password', '')).strip()

    # Opera varsayılan kullanıcısı
    if 'default_opera_user' in d:
        current_cfg['default_opera_user'] = str(d['default_opera_user']).strip()

    ok_saved = config.save_local_config(current_cfg)
    if ok_saved:
        return ok(current_cfg, message='Bireysel ayarlarınız başarıyla kaydedildi.')
    return fail('Ayarlar kaydedilirken bir hata oluştu.')


# ----------------------------- Opera API -----------------------------

@app.route('/api/opera/fetch-merns', methods=['POST'])
def api_opera_fetch_merns():
    result = opera_module.fetch_merns()
    if result['success']:
        return ok(result['data'])
    return fail(result['error'], 500)


@app.route('/api/opera/start', methods=['POST'])
def api_opera_start():
    d = body()
    tckn = str(d.get('tckn', '')).strip()
    dt = str(d.get('dt', '')).strip()
    iccid_no = str(d.get('iccid', '')).strip()
    raw_opts = d.get('options') or {}
    nr = bool(raw_opts.get('nr', False))
    volte = bool(raw_opts.get('volte', True if not raw_opts else False)) or nr
    vowifi = bool(raw_opts.get('vowifi', True if not raw_opts else False))
    lte = bool(raw_opts.get('lte', True if not raw_opts else False)) or nr or volte or vowifi
    wcdma = bool(raw_opts.get('wcdma', True if not raw_opts else False)) or lte
    gsm = bool(raw_opts.get('gsm', True if not raw_opts else False)) or wcdma
    options = {
        'gsm': gsm,
        'wcdma': wcdma,
        'lte': lte,
        'nr': nr,
        'volte': volte,
        'vowifi': vowifi,
    }
    opera_user = str(d.get('opera_user', '')).strip()
    if opera_user:
        options['opera_user'] = opera_user
    pos_pre = str(d.get('pos_pre', '')).strip()
    if pos_pre:
        options['pos_pre'] = pos_pre

    if not re.fullmatch(r'\d{11}', tckn):
        return fail('TCKN 11 haneli rakam olmalı.')
    if not re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}', dt):
        return fail('Doğum tarihi GG/AA/YYYY formatında olmalı.')
    if not re.fullmatch(r'\d{19,20}', iccid_no):
        return fail('ICCID 19-20 haneli rakam olmalı.')

    task_id = opera_module.start_activation(tckn, dt, iccid_no, options=options)
    return ok({'task_id': task_id}, message='Aktivasyon başlatıldı.')


@app.route('/api/opera/start-multi', methods=['POST'])
def api_opera_start_multi():
    d = body()
    items = d.get('items') or []
    if not isinstance(items, list) or len(items) == 0:
        return fail('En az bir adet ICCID seçmelisiniz.')

    valid_items = []
    for it in items:
        iccid_no = str(it.get('iccid', '')).strip()
        if re.fullmatch(r'\d{19,20}', iccid_no):
            valid_items.append({
                'iccid': iccid_no,
                'msisdn': str(it.get('msisdn', '')).strip(),
                'pos_pre': str(it.get('pos_pre', '')).strip(),
                'owner': str(it.get('owner', '')).strip(),
            })

    if not valid_items:
        return fail('Geçerli formatta (19-20 haneli) ICCID bulunamadı.')

    raw_opts = d.get('options') or {}
    nr = bool(raw_opts.get('nr', False))
    volte = bool(raw_opts.get('volte', True if not raw_opts else False)) or nr
    vowifi = bool(raw_opts.get('vowifi', True if not raw_opts else False))
    lte = bool(raw_opts.get('lte', True if not raw_opts else False)) or nr or volte or vowifi
    wcdma = bool(raw_opts.get('wcdma', True if not raw_opts else False)) or lte
    gsm = bool(raw_opts.get('gsm', True if not raw_opts else False)) or wcdma
    options = {
        'gsm': gsm,
        'wcdma': wcdma,
        'lte': lte,
        'nr': nr,
        'volte': volte,
        'vowifi': vowifi,
    }
    opera_user = str(d.get('opera_user', '')).strip()
    if opera_user:
        options['opera_user'] = opera_user
    pos_pre = str(d.get('pos_pre', '')).strip()
    if pos_pre:
        options['pos_pre'] = pos_pre

    task_id = opera_module.start_multi_activation(valid_items, options=options)
    return ok({'task_id': task_id, 'count': len(valid_items)}, message=f'{len(valid_items)} hat için çoklu aktivasyon başlatıldı.')


@app.route('/api/opera/status/<task_id>')
def api_opera_status(task_id):
    offset = request.args.get('offset', 0, type=int)
    status = opera_module.get_task_status(task_id, offset)
    if not status:
        return fail('Görev bulunamadı.', 404)
    return ok(status)


@app.route('/api/opera/stop/<task_id>', methods=['POST'])
def api_opera_stop(task_id):
    result = opera_module.stop_activation(task_id)
    if result['success']:
        return ok(None, message=result['message'])
    return fail(result['error'])


@app.route('/api/opera/screenshot/<task_id>', methods=['POST'])
def api_opera_screenshot(task_id):
    result = opera_module.take_task_screenshot(task_id)
    if result['success']:
        return ok({'screenshot_url': result['screenshot_url']})
    return fail(result['error'])


# ----------------------------- ICCID & User API -----------------------------

@app.route('/api/users', methods=['GET'])
def api_users_list():
    return ok(_get_tp_users_view())


@app.route('/api/users', methods=['POST'])
def api_users_add():
    import ICCID as ICCID_Func
    d = body()
    domain_user = str(d.get('user', '')).strip()
    password = str(d.get('password', '')).strip()
    name = str(d.get('name', '')).strip()

    if not domain_user or not password:
        return fail('Domain ID (Sicil No) ve Şifre alanları zorunludur.')

    # Kullanıcı adı girilmediyse TestPortal üzerinden doğrula ve tam adı çek
    if not name:
        auth_res = auth_module.authenticate_testportal(domain_user, password)
        if not auth_res.get('success'):
            return fail(auth_res.get('error', 'TestPortal girişi doğrulanamadı. Sicil veya şifre hatalı.'))
        name = auth_res.get('name') or domain_user

    ICCID_Func.add_user(name, domain_user, password)
    return ok(_get_tp_users_view(), message=f'{name} başarıyla eklendi.')


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def api_users_delete(user_id):
    import ICCID as ICCID_Func
    users_map = ICCID_Func.load_users()
    owner_name = users_map.get(int(user_id), {}).get('Name')
    deleted = ICCID_Func.delete_user(user_id)
    if not deleted:
        return fail('Kullanıcı bulunamadı.', 404)
    if owner_name:
        iccid_module.remove_owner_lines_from_cache(owner_name)
    return ok(_get_tp_users_view(), message='Kullanıcı silindi.')


@app.route('/api/iccid/list')
def api_iccid_list():
    return ok(iccid_module.load_cached_lines())


@app.route('/api/iccid/fetch', methods=['POST'])
def api_iccid_fetch():
    d = body()
    user_ids = d.get('user_ids', d.get('user_id', 'all'))
    result = iccid_module.fetch_iccids(user_ids=user_ids)
    if result['success']:
        return ok(result['data'], all_lines=result.get('all_lines', result['data']))
    return fail(result['error'], 500)


@app.route('/api/iccid/check', methods=['POST'])
def api_iccid_check():
    msisdn = str(body().get('msisdn', '')).strip()
    if not msisdn:
        return fail('MSISDN gerekli.')
    result = iccid_module.check_iccid_status(msisdn)
    if result['success']:
        return ok(result['data'])
    return fail(result['error'], 500)


@app.route('/api/iccid/clean', methods=['POST'])
def api_iccid_clean():
    d = body()
    msisdns = d.get('msisdns', [])
    if isinstance(msisdns, str):
        msisdns = [msisdns]
    result = iccid_module.clean_iccids(msisdns)
    if result['success']:
        return ok(result['data'])
    return fail(result['error'], 500)


# ----------------------------- MDM/ES API (taslak) -----------------------------

@app.route('/api/mdm/fetch-imsi', methods=['POST'])
def api_mdm_fetch_imsi():
    msisdn = str(body().get('msisdn', '')).strip()
    if not re.fullmatch(r'\d{10}', msisdn):
        return fail('MSISDN 10 haneli olmalı (ör. 5012634460).')
    result = db_helper.get_imsi_by_msisdn(msisdn)
    if result['success']:
        return ok({'imsi': result['imsi']})
    return fail(result['error'], 500)


@app.route('/api/mdm/register', methods=['POST'])
def api_mdm_register():
    d = body()
    imei = str(d.get('imei', '')).strip()
    imsi = str(d.get('imsi', '')).strip()
    msisdn = str(d.get('msisdn', '')).strip()
    target = str(d.get('target', 'both')).strip()
    manufacturer = str(d.get('manufacturer', '')).strip() or None
    model = str(d.get('model', '')).strip() or None
    if not (imei and imsi and msisdn):
        return fail('IMEI, IMSI ve MSISDN alanlarının hepsi gerekli.')
    result = mdm_es_module.register_device(
        imei=imei,
        imsi=imsi,
        msisdn=msisdn,
        target=target,
        manufacturer=manufacturer,
        model=model
    )
    return ok({'task_id': result['task_id']}, message=result['message'])


@app.route('/api/mdm/status/<task_id>')
def api_mdm_status(task_id):
    task = mdm_es_module.get_task_status(task_id)
    if not task:
        return fail('Görev bulunamadı.', 404)
    has_screen = bool(task.get('_page'))
    return ok({
        'status': task['status'],
        'message': task['message'],
        'progress': task['progress'],
        'has_screen': has_screen
    })


@app.route('/api/mdm/screen/<task_id>')
def api_mdm_screen(task_id):
    img_bytes = mdm_es_module.get_task_screenshot(task_id)
    if not img_bytes:
        return ('', 204)
    return Response(img_bytes, mimetype='image/jpeg', headers={
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    })


@app.route('/api/mdm/click/<task_id>', methods=['POST'])
def api_mdm_click(task_id):
    d = body()
    x = d.get('x')
    y = d.get('y')
    if x is None or y is None:
        return fail('x ve y koordinatları gerekli.')
    success = mdm_es_module.click_task_screen(task_id, x, y)
    return ok({'clicked': success})


# ----------------------------- Sistem & Güncelleme API -----------------------------

@app.route('/api/system/version', methods=['GET'])
def api_system_version():
    return ok({'version': update_module.get_current_version_info()})


@app.route('/api/system/check-update', methods=['POST'])
def api_system_check_update():
    res = update_module.check_for_updates()
    if res.get('error'):
        return fail(res['error'], 500)
    return ok(res)


@app.route('/api/system/apply-update', methods=['POST'])
def api_system_apply_update():
    res = update_module.apply_update()
    if not res.get('success'):
        return fail(res.get('error', 'Güncelleme uygulanamadı.'), 500)
    return ok(res, message=res.get('message', 'Güncelleme tamamlandı.'))


if __name__ == '__main__':
    # threaded=True: uzun süren Playwright istekleri diğer istekleri bloklamasın
    # host=127.0.0.1: debug modunda Werkzeug konsolu ağa açılmasın (uzaktan kod çalıştırma riski)
    app.run(debug=True, host='127.0.0.1', port=5000, threaded=True)
