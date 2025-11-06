from flask import Flask, render_template, request, jsonify
import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime
import json

# Configurar paths absolutos para templates y static
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))

# Configurar credenciales de Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SHEET_NAME = 'OT_Records'  # Nombre de tu hoja de Google Sheets

def get_google_sheets_client():
    """Inicializa el cliente de Google Sheets usando credenciales del ambiente"""
    try:
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
            creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"Error al conectar con Google Sheets: {e}")
        return None

def get_spreadsheet():
    """Obtiene la hoja de cálculo por nombre"""
    client = get_google_sheets_client()
    if not client:
        return None
    
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    try:
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        return worksheet
    except gspread.exceptions.WorksheetNotFound:
        print(f"La hoja '{SHEET_NAME}' no existe. Creándola...")
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=9)
        headers = ['Agent Name', 'Date', 'From', 'To', 'Reason', '20k Bonus', 'Holiday?', 'Overnight?', 'Total Time']
        worksheet.append_row(headers)
        return worksheet
    except Exception as e:
        print(f"Error al obtener la hoja: {e}")
        return None

# Lista de agentes
AGENTS = [
    "Juan Pérez", "María García", "Carlos López", "Ana Martínez",
    "Pedro Rodríguez", "Luis Fernández", "Carmen Ruiz", "José Morales"
]

@app.route('/')
def index():
    return render_template('index.html', agents=AGENTS)

@app.route('/submit', methods=['POST'])
def submit_overtime():
    try:
        data = request.json
        if not all(k in data for k in ['agent', 'date', 'from_hour', 'from_minute', 'to_hour', 'to_minute']):
            return jsonify({'success': False, 'message': 'Datos incompletos'}), 400

        from_minutes = int(data['from_hour']) * 60 + int(data['from_minute'])
        to_minutes = int(data['to_hour']) * 60 + int(data['to_minute'])
        total_minutes = to_minutes - from_minutes

        if total_minutes <= 0:
            return jsonify({'success': False, 'message': 'La hora de fin debe ser después de la hora de inicio'}), 400

        hours = total_minutes // 60
        minutes = total_minutes % 60
        from_time = f"{int(data['from_hour']):02d}:{int(data['from_minute']):02d}"
        to_time = f"{int(data['to_hour']):02d}:{int(data['to_minute']):02d}"
        total_time = f"{hours}h {minutes}m"

        row = [
            data['agent'], data['date'], from_time, to_time,
            data.get('reason', 'Scheduled OT'), data.get('bonus', 'No'),
            'Yes' if data.get('holiday', False) else 'No',
            'Yes' if data.get('overnight', False) else 'No', total_time
        ]

        sheet = get_spreadsheet()
        if not sheet:
            return jsonify({'success': False, 'message': 'Error al conectar con Google Sheets'}), 500

        sheet.append_row(row)

        return jsonify({'success': True, 'message': f'Registro guardado: {data["agent"]} - {total_time}'})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'}), 500

@app.route('/get_totals', methods=['POST'])
def get_totals():
    try:
        data = request.json
        agent = data.get('agent')
        sheet = get_spreadsheet()
        if not sheet:
            return jsonify({'success': False, 'message': 'Error al conectar con Google Sheets'}), 500

        records = sheet.get_all_records()
        filtered = [r for r in records if r.get('Agent Name') == agent]
        total_minutes = 0
        rows = []

        for record in filtered:
            time_str = record.get('Total Time', '0h 0m')
            parts = time_str.replace('h', '').replace('m', '').split()
            if len(parts) >= 2:
                total_minutes += int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 1:
                total_minutes += int(parts[0]) * 60

            rows.append({
                'Date': record.get('Date', ''),
                'From': record.get('From', ''),
                'To': record.get('To', ''),
                'Hours': time_str,
                'Reason': record.get('Reason', ''),
                'Bonus': record.get('20k Bonus', ''),
                'Holiday': record.get('Holiday?', ''),
                'Overnight': record.get('Overnight?', '')
            })

        total_hours = total_minutes // 60
        total_mins = total_minutes % 60

        return jsonify({
            'success': True,
            'total_hours': total_hours,
            'total_minutes': total_mins,
            'rows': rows
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
