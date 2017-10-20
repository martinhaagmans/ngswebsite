import os
import json
from flask import render_template, flash, redirect, url_for, request, send_from_directory
from werkzeug.utils import secure_filename

from app import app
from .forms import NewTestForm, NewLotForm
from collections import OrderedDict

import sys
sys.path.append('/home/manager/Documents/ngsscriptlibrary')

from ngsscriptlibrary import TargetDatabase, TargetFiles, TargetAnnotation, SampleSheet

TARGETS = '/home/manager/Documents/ngstargets/'
DB = '/home/manager/Documents/ngstargets/varia/capinfo.sqlite'

def boolean_to_number(x):
    if x == 'False':
        x = 0
    elif not x:
        x = 0
    elif x == 'True':
        x = 1
    elif x:
        x = 1
    return x

@app.route('/')
@app.route('/index')
def intro():
    return render_template('index.html')

@app.route('/diagnostiek')
def show_all_tests():
    T = TargetDatabase(DB)
    tests = T.get_all_tests()
    tests.sort()
    d = OrderedDict()
    for test in tests:
        d[test] = T.get_active_capture_for_test(test)
    return render_template('showalltests.html', tests=d)


@app.route('/diagnostiek/<path:test>')
def show_testinfo(test):
    T = TargetDatabase(DB)
    tests = T.get_all_tests()
    if test not in tests:
        flash('Niet gevonden')
        return redirect(url_for('show_all_tests'))
    caps = T.get_all_captures_for_test(test)

    d = T.get_all_info_for_test(test)


    for i in ['printcnv', 'mozaiekdetectie']:
        if d['capdb'][i] == 1:
            d['capdb'][i] = 'Ja'
        elif d['capdb'][i] == 0:
            d['capdb'][i] = 'Nee'
    if d['genes']['panelsize'] is None:
        d['genes']['panelsize'] = 0
    if d['capdb']['panel'] == 'False':
        d['capdb']['panel'] = 'Geen'
    if d['capdb']['panel'] == 'OVRv1':
        d['genes']['panelsize'] = 0
    if d['genes']['agenen'] == [] and d['genes']['cgenen'] == []:
        d['genes']['agenen'] = d['genes']['genen']

    return render_template('showtest.html',
                            c=d['capdb'],g=d['genes'], caps=caps)

@app.route('/diagnostiek/nieuw', methods=['GET', 'POST'])
def add_test():

    form = NewTestForm()
    if form.validate_on_submit():

        if not str(form.oid.data).startswith('OID'):
            form.oid.data = 'OID{}'.format(form.oid.data)
        if form.pakket.data == '':
            form.pakket.data = form.capture.data
        if form.panel.data == '':
            form.panel.data = 'False'

        sql_info = '''INSERT INTO capdb
        (genesiscode, aandoening, capture, pakket, panel, OID, lot, actief,
        verdund, cnvdetectie, printcnv, mozaiekdetectie)
        VALUES ('{}', '{}', '{}', '{}', '{}', '{}', {}, {}, {}, {}, {}, {})
        '''.format(form.genesis.data, form.aandoening.data, form.capture.data,
        form.pakket.data, form.panel.data, form.oid.data, form.lotnummer.data,
        boolean_to_number(form.actief.data),
        boolean_to_number(form.verdund.data),
        boolean_to_number(form.cnvdetectie.data),
        boolean_to_number(form.printcnv.data),
        boolean_to_number(form.mozaiekdetectie.data))
        # print(sql_info, form.genesis.data)
        T = TargetDatabase(DB)
        T.change(sql_info)
        # f = form.capturetarget.data
        capturetarget = secure_filename(form.capturetarget.data.filename)
        form.capturetarget.data.save(os.path.join(app.config['UPLOAD_FOLDER'],
                                                  capturetarget))

        capturegenen = secure_filename(form.capturegenen.data.filename)
        form.capturegenen.data.save(os.path.join(app.config['UPLOAD_FOLDER'],
                                                 capturegenen))
        TF = TargetFiles(str(form.genesis.data), TARGETS,
                         bedfile=os.path.join(app.config['UPLOAD_FOLDER'],
                                                  capturetarget))
        capturegenen =  TF.genelist(os.path.join(app.config['UPLOAD_FOLDER'],
                                                 capturegenen))

        flash(capturegenen)
        return redirect(url_for('show_all_tests'))

    return render_template('addtest.html', form=form)

@app.route('/captures/<path:cap>', methods=['GET', 'POST'])
def show_tests_for_cap(cap):
    T = TargetDatabase(DB)
    tests = T.get_all_tests_for_capture(cap)
    lotnrs = T.get_all_lotnrs_for_capture(cap)
    form = NewLotForm()
    if form.validate_on_submit():
        for test in tests:
            sql = '''INSERT INTO capdb
            (genesiscode, aandoening, capture, pakket, panel, OID, lot, actief,
            verdund, cnvdetectie, printcnv, mozaiekdetectie)
            SELECT genesiscode, aandoening, capture, pakket, panel, OID, {},
            actief, verdund, cnvdetectie, printcnv, mozaiekdetectie
            FROM capdb
            WHERE genesiscode = '{}'
            '''.format(form.lotnummer.data, test)
            T.change(sql)
            flash(sql)
        return render_template('index.html')
    return render_template('showcap.html', cap=cap, tests=tests,
                                           form=form, lotnrs=lotnrs)

@app.route('/createsamplesheet', methods=['GET', 'POST'])
def upload_labexcel():
    downloads = ['barcode_pipetteerschema.txt', 'samplesheet.csv']
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        nullijst_todo = request.files['file']

        if nullijst_todo.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if nullijst_todo:
            filename = secure_filename(nullijst_todo.filename)
            uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
            nullijst_todo.save(os.path.join(uploads, filename))
            S = SampleSheet(os.path.join(uploads, filename), 'DL070',
                            os.path.join(uploads, 'SampleSheet.csv'))

            S.write_files()
            return redirect(url_for('uploaded_file',
                                 filename='SampleSheet.csv'))

            # except KeyError as e:
            #     flash('Barcode bestaat niet.', e)
            #     return render_template('uploadlabexcel.html')
            # else:
            #     return redirect(url_for('uploaded_file',
            #                          filename='SampleSheet.csv'))
    return render_template('uploadlabexcel.html')


@app.route('/created/<filename>')
def uploaded_file(filename):
    uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    return send_from_directory(directory=uploads, filename=filename)
