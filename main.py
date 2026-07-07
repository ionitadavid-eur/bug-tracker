from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)
DB_PATH = "bugs.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
                 CREATE TABLE IF NOT EXISTS bugs
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     title
                     TEXT
                     NOT
                     NULL,
                     description
                     TEXT
                     NOT
                     NULL,
                     steps
                     TEXT
                     NOT
                     NULL,
                     expected
                     TEXT
                     NOT
                     NULL,
                     actual
                     TEXT
                     NOT
                     NULL,
                     environment
                     TEXT
                     NOT
                     NULL,
                     priority
                     TEXT
                     NOT
                     NULL,
                     status
                     TEXT
                     NOT
                     NULL
                     DEFAULT
                     'Open',
                     date_reported
                     TEXT
                     NOT
                     NULL
                 )
                 ''')
    conn.commit()
    conn.close()


@app.route('/')
def index():
    conn = get_db()
    status_filter = request.args.get('status', 'All')
    priority_filter = request.args.get('priority', 'All')

    # Stats for dashboard
    total = conn.execute('SELECT COUNT(*) FROM bugs').fetchone()[0]
    open_count = conn.execute('SELECT COUNT(*) FROM bugs WHERE status = "Open"').fetchone()[0]
    in_progress_count = conn.execute('SELECT COUNT(*) FROM bugs WHERE status = "In Progress"').fetchone()[0]
    fixed_count = conn.execute('SELECT COUNT(*) FROM bugs WHERE status = "Fixed"').fetchone()[0]
    high_count = conn.execute('SELECT COUNT(*) FROM bugs WHERE priority = "High"').fetchone()[0]

    query = 'SELECT * FROM bugs WHERE 1=1'
    params = []

    if status_filter != 'All':
        query += ' AND status = ?'
        params.append(status_filter)
    if priority_filter != 'All':
        query += ' AND priority = ?'
        params.append(priority_filter)

    bugs = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('index.html', bugs=bugs, status_filter=status_filter,
                           priority_filter=priority_filter, total=total,
                           open_count=open_count, in_progress_count=in_progress_count,
                           fixed_count=fixed_count, high_count=high_count)


@app.route('/add', methods=['GET', 'POST'])
def add_bug():
    duplicate = None
    if request.method == 'POST':
        title = request.form['title']
        conn = get_db()

        # Check for duplicate
        existing = conn.execute('SELECT * FROM bugs WHERE LOWER(title) LIKE ?',
                                ('%' + title.lower()[:20] + '%',)).fetchone()

        if existing and 'confirm' not in request.form:
            duplicate = existing
            conn.close()
            return render_template('add_bug.html', duplicate=duplicate, form_data=request.form)

        conn.execute('''
                     INSERT INTO bugs (title, description, steps, expected, actual, environment, priority, status,
                                       date_reported)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                     ''', (
                         request.form['title'],
                         request.form['description'],
                         request.form['steps'],
                         request.form['expected'],
                         request.form['actual'],
                         request.form['environment'],
                         request.form['priority'],
                         request.form['status'],
                         request.form['date_reported']
                     ))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('add_bug.html', duplicate=None, form_data=None)


@app.route('/bug/<int:bug_id>')
def view_bug(bug_id):
    conn = get_db()
    bug = conn.execute('SELECT * FROM bugs WHERE id = ?', (bug_id,)).fetchone()
    conn.close()
    if bug is None:
        return "Bug not found", 404
    return render_template('view_bug.html', bug=bug)


@app.route('/update/<int:bug_id>', methods=['POST'])
def update_status(bug_id):
    conn = get_db()
    conn.execute('UPDATE bugs SET status = ? WHERE id = ?',
                 (request.form['status'], bug_id))
    conn.commit()
    conn.close()
    return redirect(url_for('view_bug', bug_id=bug_id))


@app.route('/delete/<int:bug_id>', methods=['POST'])
def delete_bug(bug_id):
    conn = get_db()
    conn.execute('DELETE FROM bugs WHERE id = ?', (bug_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/export')
def export_csv():
    import csv
    import io
    conn = get_db()
    bugs = conn.execute('SELECT * FROM bugs').fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Title', 'Description', 'Steps', 'Expected', 'Actual', 'Environment', 'Priority', 'Status', 'Date Reported'])
    for bug in bugs:
        writer.writerow([bug['id'], bug['title'], bug['description'], bug['steps'],
                         bug['expected'], bug['actual'], bug['environment'],
                         bug['priority'], bug['status'], bug['date_reported']])

    output.seek(0)
    from flask import Response
    return Response(output, mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=bug_report.csv"})

@app.route('/edit/<int:bug_id>', methods=['GET', 'POST'])
def edit_bug(bug_id):
    conn = get_db()
    if request.method == 'POST':
        conn.execute('''
            UPDATE bugs SET title=?, description=?, steps=?, expected=?, actual=?,
            environment=?, priority=?, status=?, date_reported=? WHERE id=?
        ''', (
            request.form['title'], request.form['description'], request.form['steps'],
            request.form['expected'], request.form['actual'], request.form['environment'],
            request.form['priority'], request.form['status'], request.form['date_reported'],
            bug_id
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('view_bug', bug_id=bug_id))
    bug = conn.execute('SELECT * FROM bugs WHERE id = ?', (bug_id,)).fetchone()
    conn.close()
    return render_template('edit_bug.html', bug=bug)

def auto_archive():
    conn = get_db()
    cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    conn.execute('''
        UPDATE bugs SET status = 'Archived' 
        WHERE status = 'Fixed' AND date_reported < ?
    ''', (cutoff,))
    conn.commit()
    conn.close()

@app.route('/archive')
def view_archived():
    conn = get_db()
    bugs = conn.execute('SELECT * FROM bugs WHERE status = "Archived"').fetchall()
    conn.close()
    return render_template('archived.html', bugs=bugs)

if __name__ == '__main__':
    init_db()
    auto_archive()
    app.run(debug=True)