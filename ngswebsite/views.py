import os
import re
import json
import uuid
import hashlib
import logging
import subprocess
from functools import wraps
from collections import OrderedDict

from flask import Flask, make_response
from flask import render_template, flash, redirect, url_for, request, session

import sys, os

ngslib = os.path.join('D:\\', 'GitHubRepos', 'ngsscriptlibrary')	
sys.path.append(ngslib)

import config as cfg

from ngsscriptlibrary import TargetDatabase
from ngsscriptlibrary import TargetAnnotation
from ngsscriptlibrary import SampleSheet
from ngsscriptlibrary import get_picard_header
from ngsscriptlibrary import boolean_to_number

app = Flask(__name__)

app.secret_key = 'supergeheim222'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = 'uploads'

HOME = cfg.HOME
TARGETS = cfg.TARGETS
DB = cfg.DB
MYSQLUSER = cfg.MYSQLUSER
check_user = cfg.USER
check_passwd = cfg.PASSWORD

log = 'samplesheets.log'
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh = logging.handlers.RotatingFileHandler(log, maxBytes=10*1024*1024, backupCount=5)
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)
logger.addHandler(fh)


def hash_password(password):
    salt = uuid.uuid4().hex
    return (hashlib.sha256(salt.encode()
            + password.encode()).hexdigest()
            + ':'
            + salt)


def check_password(hashed_password, user_password):
    password, salt = hashed_password.split(':')
    return (password == hashlib.sha256(salt.encode()
            + user_password.encode()).hexdigest())


def logged_in(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('logged_in') is not None:
            return f(*args, **kwargs)
        else:
            flash('Niet ingelogd.', 'error')
            next_url = request.url
            login_url = '{}?next={}'.format(url_for('do_connaiseur_login'),
                                            next_url)
            return redirect(login_url)
    return decorated_function


def download_genelist(todo_list, d, genesis):
    pakket = todo_list['pakket']
    panel = todo_list['panel']
    genes = d['pakketten'][pakket][0][1]
    out = list()
    if panel is not None:
        agenes = d['panels'][panel][0][1]
        cd = 'attachment; filename={}.{}.{}.csv'.format(genesis, pakket,
                                                        panel)
        for gene in genes:
            if gene in agenes:
                out.append('{},A'.format(gene))
            elif gene not in agenes:
                out.append('{},C'.format(gene))
    elif panel is None:
        cd = 'attachment; filename={}.{}.csv'.format(genesis, pakket)
        for gene in genes:
            out.append('{},A'.format(gene))
    r = make_response('\n'.join(out))
    r.headers['Content-Disposition'] = cd
    r.mimetype = 'text/csv'
    return r


def download_target(targetname, targetsoort):
    out = list()
    target = os.path.join(TARGETS, targetsoort,
                          '{}_target.bed'.format(targetname))
    with open(target, 'r') as f:
        for line in f:
            out.append(line.strip())

    cd = 'attachment; filename={}_target.bed'.format(targetname)
    r = make_response('\n'.join(out))
    r.headers['Content-Disposition'] = cd
    r.mimetype = 'text/csv'
    return r


@app.route('/')
def intro():
    return render_template('index.html')


@app.route('/login/', methods=['GET', 'POST'])
def do_connaiseur_login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        if user == check_user and check_password(check_passwd, pwd):
            session['logged_in'] = True
            next_url = request.args.get('next')
            return redirect(next_url)
        else:
            flash('Verkeerde gebruiker of wachtwoord.', 'error')
            return render_template('login.html')
    return render_template('login.html')


@app.route('/uitleg/database/')
def database_explained():
    return render_template('explanation_database.html')


@app.route('/uitleg/pipeline/')
def pipeline_explained():
    return render_template('explanation_pipeline.html')


@app.route('/uitleg/naamgeving/')
def nomenclature_explained():
    return render_template('explanation_nomenclature.html')


@app.route('/uitleg/samplesheet/')
def samplesheet_explained():
    return render_template('explanation_samplesheet.html')


@app.route('/uitleg/pipeline/snv')
def std_pipe():
    return render_template('explanation_pipeline_vars.html')


@app.route('/uitleg/pipeline/cnv')
def cnv_pipe():
    return render_template('explanation_pipeline_cnv.html')


@app.route('/uitleg/pipeline/mosa')
def mosaic_pipe():
    return render_template('explanation_pipeline_mosa.html')

@app.route('/uitleg/pipeline/qc')
def qc_pipe():
    return render_template('explanation_pipeline_qc.html')


@app.route('/nieuw/')
def new_menu():
    return render_template('connoimenu.html')


@app.route('/diagnostiek/')
def show_all_tests():
    T = TargetDatabase(DB)
    tests = T.get_all_tests()
    tests.sort()
    tmp = dict()
    capture_test = dict()

    for test in tests:
        tmp[test] = T.get_info_for_genesis(test)
        cap = tmp[test]['capture']
        capture_test[cap] = test
    d = OrderedDict()
    captures = list(capture_test.keys())
    captures.sort()
    for cap in captures:
        for test in tests:
            if tmp[test]['capture'] == cap:
                d[test] = tmp[test]
    return render_template('showalltests.html', tests=d)


@app.route('/diagnostiek/<genesis>', methods=['GET', 'POST'])
def show_testinfo(genesis):
    T = TargetDatabase(DB)
    tests = T.get_all_tests()
    if genesis not in tests:
        flash('{} niet gevonden'.format(genesis))
        return redirect(url_for('show_all_tests'))

    d = dict()
    d['captures'] = dict()
    d['pakketten'] = dict()
    d['panels'] = dict()

    caps = T.get_all_captures_for_genesis(genesis)
    caps = [T.get_all_versions_for_capture(cap) for cap in caps]
    for cap in caps:
        for vcap in cap:
            d['captures'][vcap] = T.get_all_info_for_vcapture(vcap)

    pakketten = T.get_all_pakketten_for_genesis(genesis)
    pakketten = [T.get_all_versions_for_pakket(p) for p in pakketten]
    for p in pakketten:
        for vp in p:
            d['pakketten'][vp] = T.get_all_info_for_vpakket(vp)

    panels = T.get_all_panels_for_genesis(genesis)
    panels = [T.get_all_versions_for_panel(p) for p in panels]
    for p in panels:
        if p is None:
            continue
        for vp in p:
            d['panels'][vp] = T.get_all_info_for_vpanel(vp)
    todo_list = T.get_info_for_genesis(genesis)

    if request.method == 'POST':
        if 'genes' in request.form:
            r = download_genelist(todo_list, d, genesis)
            return r
        else:
            data = request.form.to_dict()
            targetname, targetsoort = list(data.keys())[0].split(':')
            r = download_target(targetname, targetsoort)
            return r

    return render_template('showtest.html', info=d, todo=todo_list)


@app.route('/diagnostiek/nieuw/', methods=['GET', 'POST'])
@logged_in
def add_test():
    T = TargetDatabase(DB)
    captures = T.get_all_captures()
    if request.method == 'POST':
        capture = request.form['capture']
        genesis = request.form['genesis']
        aandoening = request.form['aandoening']
        if request.form['pakket'] != '':
            pakket = request.form['pakket']
        elif request.form['pakket'] == '':
            pakket = capture
        if request.form['panel'] != '':
            panel = request.form['panel']
        elif request.form['panel'] == '':
            panel = None

        T.change("""INSERT INTO genesis (genesis, capture, pakket, panel,
        cnvscreening, cnvdiagnostiek, mozaiekdiagnostiek)
        VALUES ('{}', '{}', '{}', '{}', 1, 0, 0)
        """.format(genesis, capture, pakket, panel))

        T.change("""INSERT INTO aandoeningen VALUES ('{}', '{}')
                 """.format(genesis, aandoening))
        return redirect(url_for('show_testinfo', genesis=genesis))

    return render_template('addtest.html', captures=captures)


@app.route('/captures/<cap>')
def show_tests_for_cap(cap):
    T = TargetDatabase(DB)
    info = T.get_all_info_for_vcapture(cap)
    genesis = T.get_all_genesiscodes_for_vcapture(cap)
    oid = list()
    for tup in info:
        o, verdund, size = tup
        oid.append(o)
    return render_template('showcap.html', oid=oid, genesis=genesis,
                           verdund=verdund, size=size, cap=cap)


@app.route('/captures/link/', methods=['GET', 'POST'])
@logged_in
def link_capture():
    T = TargetDatabase(DB)
    captures = T.get_all_captures()
    gcodes = T.get_all_tests()
    if request.method == 'POST':
        capture = request.form['capture']
        gcodes = request.form.getlist('test')
        for gc in gcodes:
            sql = """UPDATE genesis
            SET capture='{}'
            WHERE genesis='{}'
            """.format(capture, gc)
            T.change(sql)
        return redirect(url_for('show_all_tests'))
    return render_template('linkcapture.html', captures=captures, tests=gcodes)


@app.route('/captures/nieuw/', methods=['GET', 'POST'])
@logged_in
def new_capture():
    if request.method == 'POST':
        T = TargetDatabase(DB)
        cap = request.form['capture'].lower()
        oid = request.form['oid']
        vcap = re.search(r'v\d+$', cap)
        if vcap is not None:
            re.sub(r'v\d+$', '', cap)
        if 'verdund' in request.form:
            verdund = request.form['verdund']
        elif 'verdund' not in request.form:
            verdund = False
        cap = cap.upper()
        verdund = boolean_to_number(verdund)
        allcaptures = T.get_all_captures()
        if cap not in allcaptures:
            versie = 1
        elif cap in allcaptures:
            versies = T.get_all_versions_for_capture(cap)
            versies = [_.split('v')[1] for _ in versies]
            versies.sort()
            versie = int(versies[-1]) + 1

        T.change("""INSERT INTO captures (capture, versie, OID, verdund, grootte)
                 VALUES ('{}', {}, {}, {}, 0)
                 """.format(cap, versie, oid, verdund))
        flash('{} toegevoegd aan database'.format(request.form['capture']))
        return redirect(url_for('new_target', cap='{}v{}'.format(cap, versie)))

    return render_template('addcapture.html')


@app.route('/captures/nieuw/target/<cap>', methods=['GET', 'POST'])
@logged_in
def new_target(cap):
    if request.method == 'POST':
        capture, versie = cap.split('v')
        targetrepo = os.path.join(TARGETS, 'captures')
        if not os.path.isdir(targetrepo):
            flash('{} bestaat niet'.format(targetrepo), 'error')
            return redirect(url_for('intro'))
        genelist = request.form['genen'].split()
        targetfile = request.files['targetfile']
        name = '{}_target.bed'.format(cap)
        targetfile.save(os.path.join(targetrepo, name))
        targetfile = os.path.join(targetrepo, name)
        T = TargetAnnotation(bedfile=targetfile, genes=genelist, host='localhost',
                             user=MYSQLUSER, db='annotation')
        notfound, notrequested = T.report_genecomp()
        annotated_bed = T.annotate_bed_and_filter_genes()
        annotated_bed_file = os.path.join(targetrepo,
                                          name.replace('.bed', '.annotated'))
        capsize = 0
        with open(annotated_bed_file, 'w') as f:
            for line in annotated_bed:
                chromosome, start, end, gene = line
                f.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                  end, gene))
                size = int(end) - int(start)
                capsize += size

        generegion_file = os.path.join(targetrepo,
                                       '{}_generegions.bed'.format(cap))
        with open(generegion_file, 'w') as f:
            for gene in genelist:
                for region in T.get_region(gene):
                    chromosome, start, end = region
                    f.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                      end, gene))

        picardheader = get_picard_header()
        picard_file = os.path.join(targetrepo,
                                   '{}_target.interval_list'.format(cap))
        with open(picard_file, 'w') as f:
            for line in picardheader:
                f.write(line)
            for line in annotated_bed:
                chromosome, start, end, gene = line
                f.write('{}\t{}\t{}\t+\t{}\n'.format(chromosome,
                                                     start, end, cap))
        sql = '''UPDATE captures
        SET grootte={}, genen='{}'
        WHERE (capture='{}' AND versie={})
        '''.format(capsize, json.dumps(genelist), capture, versie)
        TargetDatabase(DB).change(sql)
        return render_template('newcapreport.html', notfound=notfound,
                               notrequested=notrequested, cap=cap)

    return render_template('addtargets.html', cap=cap)


@app.route('/pakketten/nieuw/', methods=['GET', 'POST'])
@logged_in
def new_pakket():
    if request.method == 'POST':
        if request.form['naam'] == '':
            flash('Geen pakket opgegeven', 'error')
            return redirect(url_for('new_pakket'))
        if request.form['genen'] == '':
            flash('Geen genen opgegeven', 'error')
            return redirect(url_for('new_pakket'))
        pakket = request.form['naam'].lower()
        genen = request.form['genen'].split()

        vpakket = re.search(r'v\d+$', pakket)
        if vpakket is not None:
            re.sub(r'v\d+$', '', pakket)
        pakket = pakket.upper()
        T = TargetDatabase(DB)
        allpakketten = T.get_all_pakketten()
        if pakket not in allpakketten:
            versie = 1
        elif pakket in allpakketten:
            versies = T.get_all_versions_for_pakket(pakket)
            versies = [_.split('v')[1] for _ in versies]
            versies.sort()
            versie = int(versies[-1]) + 1

        vcapture = T.get_capture_for_pakket(pakket)
        capture, capversie = vcapture.split('v')
        capgenen = T.get_genes_for_vcapture(vcapture)
        notfound = list()
        for g in genen:
            if g not in capgenen:
                notfound.append(g)

        if len(notfound) > 0:
            flash('{} niet in capture target'.format(', '.join(notfound)),
                  'error')
            return redirect(url_for('new_pakket'))

        sql = """INSERT INTO pakketten (pakket, versie, genen)
                 VALUES ('{}', {}, '{}')
                 """.format(pakket, versie,  json.dumps(genen))
        T.change(sql)

        if capture == pakket:
            sql = """UPDATE pakketten
            SET grootte=(SELECT grootte
                         FROM captures
                         WHERE (capture='{}' AND versie={}))
            WHERE (pakket='{}' and versie={})
            """.format(capture, int(capversie), pakket, versie)
            T.change(sql)
        else:
            targetrepo = os.path.join(TARGETS, 'pakketten')
            if not os.path.isdir(targetrepo):
                flash('{} bestaat niet'.format(targetrepo), 'error')
                return redirect(url_for('intro'))

            annoted_bed = os.path.join(TARGETS, 'captures',
                                       '{}_target.annotated'.format(vcapture)
                                       )
            cap_generegions = os.path.join(TARGETS, 'captures',
                                           '{}_generegions.bed'.format(vcapture))
            pakketbed = os.path.join(targetrepo,
                                     '{}v{}_target.bed'.format(pakket, versie))
            pakket_generegs = os.path.join(targetrepo,
                                           '{}v{}_generegions.bed'.format(pakket,
                                                                          versie))
            TA = TargetAnnotation(annoted_bed)
            size = 0

            with open(pakketbed, 'w') as f:
                for line in TA.bed:
                    chromosome, start, end, gen = line
                    if gen in genen:
                        f.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                          end, gen))
                        size += int(end) - int(start)
                for gen in genen:
                    if ':' in gen and '-' in gen:
                        chromosome, startend = chromosome.split(':')
                        start, end = startend.split('-')
                        f.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                          end, 'EXTRA'))
                        size += int(end) - int(start)

            with open(cap_generegions) as f, open(pakket_generegs, 'w') as fout:
                for line in f:
                    chromosome, start, end, gen = line.split()
                    if gen in genen:
                        fout.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                             end, gen))
            sql = """UPDATE pakketten
            SET grootte={}
            WHERE (pakket='{}' AND versie={})
            """.format(size, pakket, int(versie))
            T.change(sql)
        return redirect(url_for('show_all_tests'))
    return render_template('addpakket.html')


@app.route('/panels/nieuw/', methods=['GET', 'POST'])
@logged_in
def new_panel():
    if request.method == 'POST':
        if request.form['naam'] == '':
            flash('Geen panel opgegeven')
            return redirect(url_for('new_panel'))
        if request.form['genen'] == '':
            flash('Geen genen opgegeven')
            return redirect(url_for('new_panel'))
        panel = request.form['naam'].lower()
        genen = request.form['genen'].split()

        vpanel = re.search(r'v\d+$', panel)
        if vpanel is not None:
            re.sub(r'v\d+$', '', panel)
            re.sub(r'typea$', '', panel)
        panel = panel.upper()
        T = TargetDatabase(DB)
        allpanels = T.get_all_panels()
        if panel not in allpanels:
            versie = 1
        elif panel in allpanels:
            versies = T.get_all_versions_for_panel(panel)
            versies = [_.split('v')[1] for _ in versies]
            versies.sort()
            versie = int(versies[-1]) + 1
        sql = """INSERT INTO panels (panel, versie, genen)
                 VALUES ('{}', {}, '{}')
                 """.format(panel, versie,  json.dumps(genen))
        T.change(sql)
        vpakket = T.get_pakket_for_panel(panel)
        pakket, _versiepakket = vpakket.split('v')
        vcapture = T.get_capture_for_pakket(pakket)
        capture, _versiecapture = vcapture.split('v')
        annoted_bed = os.path.join(TARGETS, 'captures',
                                   '{}_target.annotated'.format(vcapture))

        if capture == pakket:
            targetrepo = os.path.join(TARGETS, 'captures')
        elif capture != pakket:
            targetrepo = os.path.join(TARGETS, 'pakketten')
        if not os.path.isdir(targetrepo):
            raise OSError('{} does not exist.'.format(targetrepo))
        corepanels = os.path.join(TARGETS, 'panels')

        panelbed = os.path.join(corepanels,
                                '{}typeAv{}.bed'.format(panel,
                                                        versie))
        TA = TargetAnnotation(annoted_bed)
        size = 0
        with open(panelbed, 'w') as f:
            for line in TA.bed:
                chromosome, start, end, gen = line
                if gen in genen:
                    f.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                      end, gen))
                    size += int(end) - int(start)
            for gen in genen:
                if ':' in gen and '-' in gen:
                    chromosome, startend = chromosome.split(':')
                    start, end = startend.split('-')
                    f.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                      end, 'EXTRA'))
                    size += int(end) - int(start)
        sql = """UPDATE panels
        SET grootte={}
        WHERE (panel='{}' AND versie={})
        """.format(size, panel, int(versie))
        T.change(sql)
        return redirect(url_for('show_all_tests'))
    return render_template('addpanel.html')


@app.route('/createsamplesheet/', methods=['GET', 'POST'])
def upload_labexcel():
    if request.method == 'POST':
        if request.form['samples'] == '':
            flash('Geen input opgegeven', 'error')
            return render_template('uploadlabexcel.html')
        if request.form['serie'] == '':
            flash('Geen serienummer opgegeven', 'error')
            return render_template('uploadlabexcel.html')

        duplicates = False
        sample_names = list()

        serie = request.form['serie']
        nullijst_todo = request.form['samples']
        if nullijst_todo:
            logger.info('Start maken samplesheet voor MS{}'.format(serie))
            uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
            with open(os.path.join(uploads, 'samplesheet.tmp'), 'w') as f, open(os.path.join(uploads, 'MS{}_sample_info.txt'.format(serie)), 'w') as f_cnv:
                for line in nullijst_todo.split('\n'):
                    if line:
                        logger.info(json.dumps(line))
                        line = line.replace(' ', '-')
                        try:
                            dnr, bc, test, cnvarchive = line.split()
                        except ValueError:
                            flash('Onvoldoende kolommen als input.', 'error')
                            return render_template('uploadlabexcel.html')
                        if not test.endswith('.NGS'):
                            flash('{} is geen geldige genesiscode'.format(test),
                                  'error')
                            return render_template('uploadlabexcel.html')
                        if not dnr.isalnum():
                            flash('{} is geen geldig sampleID'.format(dnr),
                                  'error')
                            return render_template('uploadlabexcel.html')

                        f.write('{}\t{}\t{}\n'.format(dnr, test, bc))
                        if dnr in sample_names:
                            duplicates = True
                        else:
                            sample_names.append(dnr)
                        if cnvarchive.lower() != 'robot' and cnvarchive.lower() != 'hand':
                            f_cnv.write('{}\t{}\t{}\n'.format(serie, dnr, cnvarchive))

            analist = request.form['analist']
            analist = analist.replace(' ', '_')
            S = SampleSheet(os.path.join(uploads, 'samplesheet.tmp'),
                            serie,
                            os.path.join(uploads, 'MS{}.csv'.format(serie)))
            S.write_files(analist=analist)
            logger.info('Einde maken samplesheet voor MS{} op verzoek {}'.format(serie, analist))
            subprocess.call(["cp", os.path.join(uploads, 'MS{}_sample_info.txt'.format(serie)),
                              "/data/dnadiag/databases/materiaalsoort"])
            if duplicates:
                flash("""Dubbele D-nummers zijn maar 1x in de samplesheet opgenomen.
                Overleg met de NGS-connaisseur om een correcte samplesheet te maken.
                """, 'warning')
            return redirect(url_for('uploaded_file',
                                    filename='MS{}.csv'.format(serie)))

    return render_template('uploadlabexcel.html')


@app.route('/faciliteit/', methods=['GET', 'POST'])
def linda_samplesheet():
    if request.method == 'POST':
        if request.form['samples'] == '':
            flash('Geen input opgegeven', 'error')
            return render_template('faciliteit.html')
        if request.form['readlength'] == '':
            flash('Geen read lengte opgegeven', 'error')
            return render_template('faciliteit.html')
        if request.form['serie'] == '':
            serie = 'Nvt'
        else:
            serie = request.form['serie']

        readlength = request.form['readlength']

        todo = request.form['samples']

        uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
        with open(os.path.join(uploads, 'samplesheet.tmp'), 'w') as f:
            for line in todo.split('\n'):
                if line:
                    dnr, bc = line.split()
                    f.write('{}\t{}\t{}\n'.format(dnr, serie, bc))

        S = SampleSheet(os.path.join(uploads, 'samplesheet.tmp'),
                        serie,
                        os.path.join(uploads, 'SampleSheetFaciliteit.csv'),
                        faciliteit=True)
        S.write_files(readlength=int(readlength))
        return redirect(url_for('uploaded_file',
                                filename='SampleSheetFaciliteit.csv'))

    return render_template('faciliteit.html')


@app.route('/createsamplesheet/created/<filename>')
def uploaded_file(filename):
    return render_template('download.html', filename=filename)


@app.route('/createsamplesheet/<path:filename>')
def download(filename):
    path = os.path.join(os.path.join(app.root_path,
                                     app.config['UPLOAD_FOLDER'],
                                     filename))

    def generate():
        with open(path) as f:
            yield from f
        os.remove(path)
    r = app.response_class(generate(), mimetype='text/csv')
    r.headers.set('Content-Disposition', 'attachment', filename=filename)
    return r


@app.route('/aantallen/')
def aantallen():
    return render_template('aantallen.html')


if __name__ == '__main__':
    app.run(debug=True)
