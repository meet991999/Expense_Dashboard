import os

from flask import Flask, request, jsonify, render_template, redirect
from werkzeug.utils import secure_filename
from pymongo import MongoClient
import re
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
import os
app = Flask(__name__)

# MongoDB setup
client = MongoClient(os.getenv('uri'))
db = client['expense_tracker_v2']
collection = db['chat_gpt_expenses']

# Regular expression pattern to extract data from text lines
# pattern = r'(\d{2}/\d{2}/\d{4}), (\d{2}:\d{2}) - ([^:]+): (\d+)/(.+)'
pattern = r'(\d{2}/\d{2}/\d{4}), (\d{2}:\d{2}) - ([^:]+): (-?\d+)/(.+)'


# Function to parse date and time strings into a datetime object
def parse_datetime(date_str, time_str):
    # Combine date and time into a single datetime object
    return datetime.strptime(f'{date_str} {time_str}', '%d/%m/%Y %H:%M')

# Route to render the HTML form
@app.route('/')
def upload_form():
    # return render_template('chat_gpt_upload.html')
    return redirect("home")
# Route to upload the file and store parsed data
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = secure_filename(file.filename)
    data = file.read().decode('utf-8')

    # Parse the file and insert records into MongoDB
    matches = re.findall(pattern, data)
    records = []
    for match in matches:
        date, time, name, amount, item = match
        print(amount," : ",name)
        # Convert date and time to a datetime object
        datetime_obj = parse_datetime(date, time)
        records.append({
            "datetime": datetime_obj,
            "name": name,
            "amount": int(amount),
            "item": item.strip()
        })

    # Insert all records into MongoDB
    if records:
        collection.insert_many(records)

    return jsonify({'message': f'{len(records)} records inserted'}), 200


# Route to filter data based on query params
@app.route('/filter', methods=['GET'])
def filter_data():
    name = request.args.get('name')
    start_date = request.args.get('start_date')  # Example: 2024-10-02
    end_date = request.args.get('end_date')  # Example: 2024-10-05
    min_amount = request.args.get('min_amount')
    max_amount = request.args.get('max_amount')

    query = {}
    if name:
        query['name'] = name
    if start_date or end_date:
        query['datetime'] = {}
        if start_date:
            query['datetime']['$gte'] = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            query['datetime']['$lte'] = datetime.strptime(end_date, '%Y-%m-%d')
    if min_amount or max_amount:
        query['amount'] = {}
        if min_amount:
            query['amount']['$gte'] = int(min_amount)
        if max_amount:
            query['amount']['$lte'] = int(max_amount)

    results = list(collection.find(query, {"_id": 0}))
    return jsonify(results), 200


@app.route('/data', methods=['GET'])
def get_data():
    name = request.args.get('name')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    min_amount = request.args.get('min_amount')
    max_amount = request.args.get('max_amount')

    query = {}

    # Handle name filter
    if name:
        query['name'] = name

    # Handle date range
    if start_date or end_date:
        query['datetime'] = {}
        if start_date:
            query['datetime']['$gte'] = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            query['datetime']['$lte'] = datetime.strptime(end_date, '%Y-%m-%d')

    # Handle amount range
    if min_amount or max_amount:
        query['amount'] = {}
        if min_amount:
            query['amount']['$gte'] = float(min_amount)  # Using float instead of int for more flexibility
        if max_amount:
            query['amount']['$lte'] = float(max_amount)

    try:
        results = list(collection.find(query, {'_id': 0}))
        return jsonify(results), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to render the HTML page with the graph
@app.route('/graph')
def display_graph():
    return render_template('chat_gpt_graph.html')

@app.route('/test-entries')
def display_entries():
    return render_template('chat_gpt_entries.html')

@app.route('/entries', methods=['GET'])
def get_entries():
    page = int(request.args.get('page', 1))
    limit = 10  # Adjust the number of entries per page
    skip = (page - 1) * limit

    # Retrieve filter parameters from the request
    min_amount = request.args.get('min_amount', type=int)
    max_amount = request.args.get('max_amount', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    name = request.args.get('name', type=str)

    # Build the filter criteria
    query = {}
    if min_amount is not None:
        query['amount'] = {'$gte': min_amount}
    if max_amount is not None:
        query['amount'] = {'$lte': max_amount} if 'amount' not in query else {'$and': [query['amount'], {'$lte': max_amount}]}
    if start_date:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        query['datetime'] = {'$gte': start_date_obj}
    if end_date:
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        query['datetime'] = query.get('datetime', {})
        query['datetime']['$lte'] = end_date_obj
    if name:
        query['name'] = {'$regex': name, '$options': 'i'}  # Case-insensitive match

    # Query the database
    entries = list(collection.find(query, {'_id': 0}).skip(skip).limit(limit))
    total_entries = collection.count_documents(query)
    total_pages = (total_entries + limit - 1) // limit  # Calculating total pages

    return jsonify({
        "entries": entries,
        "page": page,
        "total_pages": total_pages
    })

@app.route('/home', methods=['GET'])
def home():
    total = collection.aggregate([
        {
            '$group': {
                '_id': None,
                'totalAmount': {'$sum': '$amount'}
            }
        }
    ])
    total_amount = list(total)
    final_ammount = total_amount[0]['totalAmount'] if total_amount else 0
    # return jsonify({'total_amount': total_amount[0]['totalAmount'] if total_amount else 0}), 200
    return render_template("chat_gpt_home.html",  final_ammount=final_ammount)

if __name__ == '__main__':
    app.run(debug=True)
