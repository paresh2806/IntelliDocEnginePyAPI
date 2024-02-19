import json
import re
import os
import collections
from turtle import update
import requests
import psycopg2
import shutil
from email import message
from email.message import Message
from flask import Flask, flash, request, redirect, url_for, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
from flask_cors import CORS
from config import config
from deepdoctection.analyzer import get_dd_analyzer
from glob import glob
from jsonedit import jsonedit
import spacy
import numpy as np
from getlocations import getlocations

# analyzer = get_dd_analyzer()
UPLOAD_FOLDER = 'Uploads'
OCR_ROOT_FOLDER = 'OCR'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg'}

app = Flask(__name__)
CORS(app)
cors = CORS(app, resources={r"/upload*": {"origins": "*"}})

app.secret_key = "secret key"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OCR_ROOT_FOLDER'] = OCR_ROOT_FOLDER


def get_db_connection():
    params = config()
    conn = psycopg2.connect(**params)
    return conn


def query_list():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        '''SELECT upload_id, file_name , file_url , ocr_status , file_timestamp from users_upload_meta ORDER by file_timestamp DESC ''')
    rows = cur.fetchall()
    cur.connection.close()
    if len(rows) > 0:

        object_list = []
        for rows in rows:
            d = collections.OrderedDict()
            d['FileNumber'] = rows[0]
            d['FileName'] = rows[1]
            d['FileURL'] = rows[2]
            d['OCRStatus'] = rows[3]
            d['TimeStamp'] = rows[4]

            object_list.append(d)
        resp = jsonify(object_list)
    else:
        resp = jsonify({"type": "success", 'msg': 'No data founds.'})

    return resp


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/file_list', methods=['GET', 'POST'])
def file_list():
    return query_list()


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    resp = ' '
    user_id = 1  # User detail [default id = 1]
    OCR_Status = 'NO'  # default val
    # print(request.method)
    if request.method == 'POST':

        file = request.files['file']

        # check if the post request has the file part
        if 'file' not in request.files or file.filename == '':
            resp = jsonify({"type": "error", "msg": 'File not found.'})
            # resp.status_code = 400

        # if user does not select file, browser also
        # submit an empty part without filename
        if request.content_length < 15000:
            resp = jsonify({"type": "error", "msg": 'Please Upload a file more than 15KB.'})
            # resp.status_code = 400.
            # return resp, resp.status_code
        elif request.content_length > 15728640:
            resp = jsonify({"type": "error", "msg": 'Maximum file size will allow only 15MB.'})
            # resp.status_code = 400
            # return resp, resp.status_code
        elif file and allowed_file(file.filename):
            conn = get_db_connection()
            cur = conn.cursor()
            ##
            filename = secure_filename(file.filename)
            Only_filename = file.filename.split('.')[0]
            Only_filename = Only_filename.replace(' ', '_')
            Localhost_file_URL = request.url_root + 'Uploads/' + filename
            Absolute_path = os.path.join(os.path.abspath(app.config['UPLOAD_FOLDER']), filename)
            Content_type = str(file.filename.split('.')[-1])
            ##
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cur.execute(
                f'''INSERT into users_upload_meta (user_id,file_name,file_url,file_path,mime_type,ocr_status) values ('{user_id}','{Only_filename}','{Localhost_file_URL}','{Absolute_path}','{Content_type}','{OCR_Status}') ''')  # this should be the format of the quary to append the data '''INSERT into file_list (file_name) values('abc');'''
            conn.commit()
            resp = jsonify({"type": "success", "msg": 'File Successfully Uploaded'})
            # resp.status_code = 201
            # print(url_for('upload_file',filename=filename))
            # return redirect(url_for('upload_file',filename=filename))
            # return resp, resp.status_code
        else:
            resp = jsonify({"type": "error", "msg": 'Allowed file types are only PDF, PNG, JPG and JPEG.'})
            # resp.status_code = 400
            # return resp, resp.status_code
        return resp
    return

    '''
        <html>
        <body>
          <form action = "http://localhost:5000/upload" method = "POST" 
             enctype = "multipart/form-data">
             <input type = "file" name = "file" />
             <input type = "submit"/>
          </form>   
        </body>
        </html>
        
        '''


@app.route('/Uploads/<filename>', methods=['GET', 'POST'])
def get_pdf(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        abort(404)


@app.route('/getOCR/', methods=['GET', 'POST'])
def OCR():
    if request.method == 'POST':
        # print(request.form)
        file_id = request.form['filenum']
        update_flag = 0
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            '''SELECT file_name , file_url, mime_type , file_path, upload_id, ocr_status from users_upload_meta WHERE upload_id={} and user_id={}'''.format(
                file_id, 1))

        rows = cur.fetchall()
        Temp_Filename = rows[0][0]
        Temp_Filename.replace(' ', '_')
        Temp_FileUrl = rows[0][1]
        Temp_FileType = rows[0][2]
        Temp_FileLocation = rows[0][3]
        Temp_FileUploadID = rows[0][4]
        OCR_status = rows[0][5]
        # print(Temp_FileLocation)
        # print(OCR_status)

        if Temp_FileType == 'png' or Temp_FileType == 'jpg' and OCR_status == 'NO':

            Temp_FileUID = f'extracted_{Temp_Filename}_{Temp_FileUploadID}'
            if not os.path.exists(app.config['OCR_ROOT_FOLDER'] + f'/Image_files/' + Temp_Filename):
                os.mkdir(app.config['OCR_ROOT_FOLDER'] + f'/Image_files/' + Temp_Filename)
                shutil.copy(Temp_FileLocation, f'OCR/Image_files/{Temp_Filename}')
                Temp_FileDIR = os.path.join(app.config['OCR_ROOT_FOLDER'] + f'/Image_files/', Temp_Filename)
                df = analyzer.analyze(path=Temp_FileDIR)
                df.reset_state()
                page = next(iter(df))
                Temp_raw_table = []
                Temp_raw_text = page.get_text()
                Temp_raw_text = Temp_raw_text.replace("'", "''")
                Temp_nlp_obj = nlp(Temp_raw_text)
                Temp_html = spacy.displacy.render(Temp_nlp_obj, style="ent", jupyter=False)
                locations = []
                locations.extend(ent.text for ent in Temp_nlp_obj.ents if ent.label_ in ['GPE'])
                locations.extend(ent.text for ent in Temp_nlp_obj.ents if ent.label_ in ['LOC'])
                unique_loc = np.unique(locations)
                print(unique_loc)
                getlocations(unique_loc, file_id)
                for i in range(len(page.tables)):
                    temp_table = page.tables[0].html
                    temp_table = temp_table.replace("'", "''")
                    # temp_table = re.escape(temp_table)
                    Temp_raw_table.append(temp_table)
                print(Temp_raw_table)
                # print(page.get_text())
                page.save()
                Result = page.viz()
                OCR_FLAG = 'YES'
                print('log')
                jsonedit(app.config[
                             'OCR_ROOT_FOLDER'] + f'''/Image_files/{Temp_Filename}/''' + Temp_Filename + '.json')

                #####-----------------------> for json combine ----------------------------------<
                with open(app.config[
                              'OCR_ROOT_FOLDER'] + f'''/Image_files/{Temp_Filename}/''' + Temp_Filename + '.json') as json_data:
                    Temp_serial_data = json.load(json_data)
                    # cur.execute(
                    #     f'''INSERT INTO users_file_metadata (upload_id, key ,value, raw_text) values ('{Temp_FileUploadID}','{Temp_FileUID}','{json.dumps(Temp_serial_data)}','{Temp_raw_text}')''')
                    if len(page.tables) > 0:
                        cur.execute(
                            f'''INSERT INTO users_file_metadata (upload_id, key , raw_text, raw_table, update_flag, html_resp) values ('{Temp_FileUploadID}','{Temp_FileUID}','{Temp_raw_text}',ARRAY{Temp_raw_table},'{update_flag}','{Temp_html}')''')
                    else:
                        cur.execute(
                            f'''INSERT INTO users_file_metadata (upload_id, key , raw_text, update_flag, html_resp) values ('{Temp_FileUploadID}','{Temp_FileUID}','{Temp_raw_text}','{update_flag}','{Temp_html}')''')

                cur.execute(
                    '''update users_upload_meta SET ocr_status='{}' where upload_id={}'''.format(str(OCR_FLAG),
                                                                                                 file_id))

                conn.commit()
                resp = jsonify({"type": "success", "msg": 'OCR performed'})
                # resp.status_code = 200


            else:
                if any(File.endswith(".json") for File in
                       os.listdir(app.config[
                                      'OCR_ROOT_FOLDER'] + f'/Image_files/' + Temp_Filename + '/')) and OCR_status == 'NO':
                    resp = jsonify({"type": "Alert", "msg": 'OCR Already Performed '})
                    # resp.status_code = 400
                else:
                    Temp_FileDIR = os.path.join(app.config['OCR_ROOT_FOLDER'] + f'/Image_files/', Temp_Filename)
                    df = analyzer.analyze(path=Temp_FileDIR)
                    df.reset_state()
                    page = next(iter(df))
                    Temp_raw_table = []
                    Temp_raw_text = page.get_text()
                    Temp_raw_text = Temp_raw_text.replace("'", "''")
                    Temp_nlp_obj = nlp(Temp_raw_text)
                    Temp_html = spacy.displacy.render(Temp_nlp_obj, style="ent", jupyter=False)
                    locations = []
                    locations.extend(ent.text for ent in Temp_nlp_obj.ents if ent.label_ in ['GPE'])
                    locations.extend(ent.text for ent in Temp_nlp_obj.ents if ent.label_ in ['LOC'])
                    unique_loc = np.unique(locations)
                    print(unique_loc)
                    getlocations(unique_loc, file_id)
                    for i in range(len(page.tables)):
                        temp_table = page.tables[0].html
                        temp_table = temp_table.replace("'", "''")
                        # temp_table = re.escape(temp_table)
                        Temp_raw_table.append(temp_table)
                    page.save()
                    Result = page.viz()

                    OCR_FLAG = 'YES'
                    print('log')
                    jsonedit(app.config[
                                 'OCR_ROOT_FOLDER'] + f'''/Image_files/{Temp_Filename}/''' + Temp_Filename + '.json')
                    with open(app.config[
                                  'OCR_ROOT_FOLDER'] + f'''/Image_files/{Temp_Filename}/''' + Temp_Filename + '.json') as json_data:
                        Temp_serial_data = json.load(json_data)
                        # cur.execute(
                        #     f'''INSERT INTO users_file_metadata (upload_id, key ,value, raw_text) values ('{Temp_FileUploadID}','{Temp_FileUID}','{json.dumps(Temp_serial_data)}','{Temp_raw_text}')''')
                        if len(page.tables) > 0:
                            cur.execute(
                                f'''INSERT INTO users_file_metadata (upload_id, key, raw_text,raw_table, update_flag,html_resp) values ('{Temp_FileUploadID}','{Temp_FileUID}','{Temp_raw_text}',ARRAY{Temp_raw_table},'{update_flag}','{Temp_html}')''')
                        else:
                            cur.execute(
                                f'''INSERT INTO users_file_metadata (upload_id, key, raw_text, update_flag,html_resp) values ('{Temp_FileUploadID}','{Temp_FileUID}','{Temp_raw_text}','{update_flag}','{Temp_html}')''')

                    cur.execute(
                        '''update users_upload_meta SET ocr_status='{}' where upload_id = {}'''.format(str(OCR_FLAG),
                                                                                                       file_id))
                    conn.commit()
                    resp = jsonify({"type": "success", "msg": 'IMAGE File secured and OCR performed'})
                    # resp.status_code = 200

        if Temp_FileType == 'pdf' and OCR_status == 'NO':
            print("File type = PDF")

            if not os.path.exists(app.config['OCR_ROOT_FOLDER'] + f'/PDF_files/' + Temp_Filename):
                os.mkdir(app.config['OCR_ROOT_FOLDER'] + f'/PDF_files/' + Temp_Filename)
                shutil.copy(Temp_FileLocation, f'OCR/PDF_files/{Temp_Filename}')
                Temp_FileDIR = os.path.join(
                    app.config['OCR_ROOT_FOLDER'] + f'/PDF_files/{Temp_Filename}/{Temp_Filename}.pdf')
                OCR_FLAG = 'YES'
                print(Temp_FileDIR)
                df = analyzer.analyze(path=Temp_FileDIR)
                df.reset_state()
                doc = iter(df)
                Merged_json = []
                print(f'Page length={len(df)}')
                for i in range(len(df)):
                    Temp_FileUID = f'Extracted_{Temp_Filename}_{Temp_FileUploadID}_page{i}'
                    print(f'Initializing OCR on page:{i}')
                    page = next(doc)
                    Temp_raw_text = []
                    Temp_raw_table = []
                    temp_table = []
                    Temp_raw_text = page.get_text()
                    Temp_raw_text = Temp_raw_text.replace("'", "''")
                    Temp_nlp_obj = nlp(Temp_raw_text)
                    Temp_html = spacy.displacy.render(Temp_nlp_obj, style="ent", jupyter=False)
                    locations = []
                    locations.extend(ent.text for ent in Temp_nlp_obj.ents if ent.label_ in ['GPE'])
                    locations.extend(ent.text for ent in Temp_nlp_obj.ents if ent.label_ in ['LOC'])
                    unique_loc = np.unique(locations)
                    print(unique_loc)
                    getlocations(unique_loc, file_id)
                    for i in range(len(page.tables)):
                        temp_table = page.tables[0].html
                        temp_table = temp_table.replace("'", "''")
                        # temp_table = re.escape(temp_table)
                        Temp_raw_table.append(temp_table)
                    # print(app.config['OCR_ROOT_FOLDER'] + f'''/PDF_files/{Temp_Filename}/{Temp_Filename}_{i}.JSON''')
                    page.save(
                        path=app.config['OCR_ROOT_FOLDER'] + f'/PDF_files/{Temp_Filename}/{Temp_Filename}_{i}.JSON')
                    jsonedit(app.config[
                                 'OCR_ROOT_FOLDER'] + f'''/PDF_files/{Temp_Filename}/{Temp_Filename}_{i}''' + '.json')
                    # with open(app.config[
                    #               'OCR_ROOT_FOLDER'] + f'''/PDF_files/{Temp_Filename}/{Temp_Filename}_{i}''' + '.json',
                    #           'rb') as json_data:
                    # # cur.execute(
                    #         f'''INSERT INTO users_file_metadata (upload_id, key ,value ,raw_text) values ('{Temp_FileUploadID}','{Temp_FileUID}','{json.dumps(json_data)}','{Temp_raw_text}')''')
                    if len(page.tables) > 0:
                        cur.execute(
                            f'''INSERT INTO users_file_metadata (upload_id, key,raw_text , raw_table, update_flag,html_resp) values ('{Temp_FileUploadID}','{Temp_FileUID}','{Temp_raw_text}',ARRAY{Temp_raw_table},'{update_flag}','{Temp_html}')''')
                        print('if executed')
                        conn.commit()
                    else:
                        cur.execute(
                            f'''INSERT INTO users_file_metadata (upload_id, key,raw_text, update_flag, html_resp) values ('{Temp_FileUploadID}','{Temp_FileUID}','{Temp_raw_text}','{update_flag}','{Temp_html}')''')
                        print('else executed')
                        conn.commit()
                # -----------------------------> for merged json ---------------<
                # Merged_json.append(json.load(json_data))

                # cur.execute(
                #     f'''INSERT INTO users_file_metadata (upload_id, key ,value) values ('{Temp_FileUploadID}','{Temp_FileUID}','{json.dumps(Merged_json)}')''')
                cur.execute(
                    '''update users_upload_meta SET ocr_status='{}' where upload_id = {}'''.format(str(OCR_FLAG),
                                                                                                   file_id))
                conn.commit()
                resp = jsonify({"type": "success", "msg": 'OCR performed'})
                # resp.status_code = 200
            else:
                resp = jsonify({"type": "alert", "msg": 'OCR Already performed'})
                # resp.status_code = 400
        return resp


# @app.route('/editOCR/', methods=['GET', 'POST'])
# def editOCR():
#     if request.method == 'POST':
#         print(request.form)
#         update_flag=0
#         file_id = request.form["filenum"]
#         conn = get_db_connection()
#         cur = conn.cursor()


#         cur.execute(
#             '''SELECT raw_text, raw_table, key, update_flag from users_file_metadata WHERE upload_id={}  order by meta_id ASC'''.format(
#                 file_id))
#         rows = cur.fetchall()
#         raw_text_value = []
#         raw_table_value = []
#         # update_value=[0][3]
#         print(rows)
#         try:
#             if len(rows)>0:
#                 for i in range(len(rows)):
#                     text_value = rows[i][0]
#                     raw_text_value.append(text_value)
#                     table_value = rows[i][1]
#                     raw_table_value.append(table_value)
#                 resp = jsonify({'raw_text': raw_text_value, 'raw_table': raw_table_value})
#             else:
#                 resp = jsonify({"type": "error", "msg": 'No data found'})

#         # return jsonify(raw_text_value)
#         except:
#             resp = jsonify({"type": "error", "msg": 'could not found the data'})
#         # return {'raw_text': raw_text_value, 'raw_table': raw_table_value}
#         return resp


@app.route('/editOCR/', methods=['GET', 'POST'])
def editOCR():
    if request.method == 'POST':
        print(request.form)
        update_flag = 0
        temp_flag = 0
        file_id = request.form["filenum"]
        conn = get_db_connection()
        cur = conn.cursor()
        raw_text_value = []
        raw_table_value = []
        try:
            cur.execute(
                '''SELECT raw_text, raw_table, update_flag from users_file_metadata WHERE upload_id={} and update_flag=true '''.format(
                    file_id))
            rows = cur.fetchall()
            raw_text_value = rows[0][0]
            raw_table_value = rows[0][1]
            resp = jsonify({'raw_text': raw_text_value, 'raw_table': raw_table_value})

        except:
            print('lol')
            # resp=jsonify({'raw_text': 'hahahahahah'})
            # resp=jsonify({'raw_text': raw_text_value, 'raw_table': raw_table_value})
            cur.execute(
                '''SELECT raw_text, raw_table from users_file_metadata WHERE upload_id={} and  key LIKE 'Extracted%' order by meta_id ASC'''.format(
                    file_id))
            rows = cur.fetchall()
            try:
                if len(rows) > 0:
                    for i in range(len(rows)):
                        text_value = rows[i][0]
                        raw_text_value.append(text_value)
                        table_value = rows[i][1]
                        raw_table_value.append(table_value)
                    resp = jsonify({'raw_text': raw_text_value, 'raw_table': raw_table_value})
                else:
                    resp = jsonify({"type": "error", "msg": 'No data found'})

            # # return jsonify(raw_text_value)
            except:
                resp = jsonify({"type": "error", "msg": 'could not found the data'})

        return resp


@app.route('/UpdateOCR/', methods=['GET', 'POST'])
def savechanges():
    if request.method == 'POST':
        # print(request.form)
        file_id = request.form["filenum"]
        file_text_field = request.form["raw_text"]
        file_text_field = file_text_field.replace("'", "''")
        file_table_field = request.form["raw_table"]
        file_table_field = file_table_field.replace("'", "''")
        Temp_nlp_obj = nlp(file_text_field)
        Temp_html = spacy.displacy.render(Temp_nlp_obj, style="ent", jupyter=False)
        locations = []
        locations.extend(ent.text for ent in Temp_nlp_obj.ents if ent.label_ in ['GPE'])
        locations.extend(ent.text for ent in Temp_nlp_obj.ents if ent.label_ in ['LOC'])
        unique_loc = np.unique(locations)
        getlocations(unique_loc, file_id)
        resp = ''
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            '''SELECT key,update_flag from users_file_metadata WHERE upload_id={} and update_flag=true order by meta_id ASC  '''.format(
                file_id))
        rows = cur.fetchall()
        # print(rows)
        if len(rows) == 1:
            try:
                # print('if 1')
                cur.execute(
                    f'''UPDATE users_file_metadata SET raw_text= '{file_text_field}',raw_table='{file_table_field}',html_resp='{Temp_html}'  where upload_id={file_id} and update_flag=true ''')
                # print(f'''UPDATE users_file_metadata SET raw_text= '{file_text_field}',raw_table='{file_table_field}' where upload_id={file_id} and update_flag=true ''')
                conn.commit()
                resp = jsonify({"type": "success", "msg": 'Data Updated'})
            except:
                resp = jsonify({"type": "error", "msg": 'unable to update data'})
        else:
            # print('if 0')
            try:
                cur.execute(
                    f'''INSERT INTO users_file_metadata (upload_id,key,raw_text,raw_table,update_flag,html_resp) values ('{file_id}','Update_{file_id}','{file_text_field}','{file_table_field}',true,'{Temp_html}')''')
                conn.commit()
                resp = jsonify({"type": "success", "msg": 'OCR Insert Updated'})
            except:
                resp = jsonify({"type": "error", "msg": 'unable to update data'})
        return resp


@app.route('/getNER/', methods=['GET', 'POST'])
def getNER():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        '''SELECT
    users_upload_meta.upload_id, users_upload_meta.file_name, users_file_metadata.html_resp
    from users_file_metadata inner
    join
    users_upload_meta
    on
    users_upload_meta.upload_id = users_file_metadata.upload_id''');

    rows = cur.fetchall()

    if len(rows) > 0:
        object_list = []
        for rows in rows:
            d = collections.OrderedDict()
            d['Fileid'] = rows[0]
            d['FileName'] = rows[1]
            d['File_entities'] = rows[2]

            object_list.append(d)
        resp = jsonify(object_list)
    else:
        resp = jsonify({"type": "success", 'msg': 'No data founds.'})

    return resp

@app.route('/getLocationsOnMap/', methods=['GET', 'POST'])
def getLocationsOnMap():
    if request.method == 'POST':
        # print(request.form)
        file_id = request.form['filenum']
        conn = get_db_connection()
        cur = conn.cursor()
        Lat = []
        Lon = []
        cur.execute(f'''select latitude, longitude from location_geom where upload_id={file_id}''')
        rows = cur.fetchall()

        if len(rows) > 0:
            object_list = []
            for rows in rows:
                d = collections.OrderedDict()
                d['Latitude'] = rows[0]
                d['Longitude'] = rows[1]

                object_list.append(d)
            resp = jsonify(object_list)
        else:
            resp = jsonify({"type": "success", 'msg': 'No data founds.'})
        return resp



if __name__ == '__main__':
    global analyzer
    analyzer = get_dd_analyzer()
    nlp = spacy.load('en_core_web_lg')
    app.run(host='0.0.0.0', port=5000, debug=True)
