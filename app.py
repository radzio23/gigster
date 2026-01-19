import uuid
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
import os
import psycopg
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

def query_db(query, params=None, fetch=True):
    with psycopg.connect(dbname="gigster_db", user="postgres", password="postgres", host="localhost", port="5432", row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            if fetch:
                return cur.fetchall()
            return None

def delete_old_image(filename, category):
    if filename and filename != 'default.png':
        file_path = os.path.join('static/images/' + category, filename)
        if os.path.exists(file_path):
            os.remove(file_path)

def save_image(file, category):
    if file and file.filename != '':
        path = os.path.splitext(secure_filename(file.filename))
        unique_name = f"{path[0]}_{uuid.uuid4().hex[:4]}{path[1]}"
        file.save(os.path.join('static/images/' + category, unique_name))
        return unique_name
    return None

@app.route('/')
def index():
    return redirect(url_for('concerts'))

@app.route('/admin/dashboard')
def dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    sprzedaz = query_db("SELECT * FROM w_sprzedaz_miesieczna;")
    oblozenie = query_db("SELECT * FROM w_oblozenie_koncertow;")
    artysci = query_db("SELECT * FROM w_popularnosc_artystow;")
    miasta = query_db("SELECT * FROM w_ranking_miast;")
    uzytkownicy = query_db("SELECT id, nazwa, rola FROM uzytkownicy ORDER BY rola, nazwa")

    return render_template('dashboard.html', 
                           sprzedaz=sprzedaz, 
                           oblozenie=oblozenie, 
                           artysci=artysci,
                           miasta=miasta,
                           uzytkownicy=uzytkownicy)



@app.route('/uzytkownicy/edytuj', methods=['POST'])
def edit_user():
    if session.get('role') != 'admin':
        return jsonify({"status": "error"}), 403
    
    user_id = request.form.get('id')
    nowa_nazwa = request.form.get('nazwa')
    nowa_rola = request.form.get('rola')
    nowe_haslo = request.form.get('haslo')

    query_db("UPDATE uzytkownicy SET nazwa=%s, rola=%s WHERE id=%s", (nowa_nazwa, nowa_rola, user_id), fetch=False)
    
    if nowe_haslo and nowe_haslo.strip() != "":
        hashed_pw = generate_password_hash(nowe_haslo)
        query_db("UPDATE uzytkownicy SET haslo=%s WHERE id=%s", (hashed_pw, user_id), fetch=False)

    flash('Dane użytkownika zostały zaktualizowane.')
    return jsonify({"status": "success"})

@app.route('/uzytkownicy/usun/<int:id>', methods=['POST'])
def delete_user(id):
    if session.get('role') != 'admin':
        return jsonify({"status": "error"}), 403
    
    if id == session.get('user_id'):
        flash('Nie możesz usunąć własnego konta!', 'error')
        return redirect(url_for('dashboard'))

    query_db("DELETE FROM uzytkownicy WHERE id = %s", (id,), fetch=False)
    flash('Użytkownik został usunięty.')
    return redirect(url_for('dashboard'))

@app.route('/koncerty')
def concerts():
    artysta_id = request.args.get('artysta')
    miejsce_id = request.args.get('miejsce')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax') == '1'

    query = """
        SELECT k.id, k.zdjecie, k.opis, k.data, k.czas, k.cena_biletu,
               m.nazwa AS miejsce, m.miasto, a.nazwa AS artysta
        FROM koncerty k 
        JOIN miejsca m ON m.id = k.id_miejsca 
        JOIN artysci a ON a.id = k.id_artysty
    """
    params = []
    filters = []
    if artysta_id:
        filters.append("k.id_artysty = %s")
        params.append(artysta_id)
    if miejsce_id:
        filters.append("k.id_miejsca = %s")
        params.append(miejsce_id)

    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY k.data DESC;"

    concerts = query_db(query, tuple(params))

    if is_ajax:
        for c in concerts:
            c['data'] = c['data'].strftime("%d.%m.%Y")
            c['czas'] = str(c['czas'])[:5]
        return jsonify(concerts)

    artists = query_db("SELECT id, nazwa FROM artysci ORDER BY nazwa")
    venues = query_db("SELECT id, nazwa FROM miejsca ORDER BY nazwa")
    return render_template('concerts.html', concerts=concerts, artists=artists, venues=venues)

@app.route('/uzytkownicy/<int:id>')
def get_user(id):
    try:
        results = query_db("SELECT id, nazwa, rola FROM uzytkownicy WHERE id = %s", (id,))
        if not results:
            return jsonify({"status": "error", "message": "Nie znaleziono artysty"}), 404
        
        return jsonify(results[0])
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route('/koncerty/dodaj', methods=['POST'])
def add_concert():
    id_artysty = request.form.get('id_artysty')
    id_miejsca = request.form.get('id_miejsca')
    data = request.form.get('data')
    czas = request.form.get('czas')
    opis = request.form.get('opis')
    file = request.files.get('file')
    cena = request.form.get('cena_biletu')

    if file:
        filename = save_image(file, 'koncerty')
    else:
        filename = 'default.png'

    query_db("INSERT INTO koncerty (id_artysty, id_miejsca, data, czas, opis, zdjecie, cena_biletu) VALUES (%s, %s, %s, %s, %s, %s, %s)", (id_artysty, id_miejsca, data, czas, opis, filename, cena), fetch=False)
    flash('Koncert dodany pomyślnie!')
    return jsonify({"status": "success", "filename": filename})

@app.route('/koncerty/<int:id>')
def get_concert(id):
    try:
        results = query_db("SELECT k.*, a.nazwa as artysta_nazwa, m.nazwa as miejsce_nazwa, m.miasto, m.adres, m.pojemnosc, (SELECT COUNT(*) FROM bilety b WHERE b.id_koncertu = k.id) as sprzedane FROM koncerty k JOIN artysci a ON k.id_artysty = a.id JOIN miejsca m ON k.id_miejsca = m.id WHERE k.id = %s", (id,))

        if not results:
            return jsonify({"status": "error", "message": "Nie znaleziono koncertu"}), 404
        
        c = results[0]

        c['data'] = c['data'].strftime("%Y-%m-%d")
        c['czas'] = str(c['czas'])[:5] 
        return jsonify(c)
    
    except Exception as e:
        print(f"Błąd serwera: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/koncerty/edytuj', methods=['POST'])
def update_concert():
    id = request.form.get('id')
    id_artysty = request.form.get('id_artysty')
    id_miejsca = request.form.get('id_miejsca')
    data = request.form.get('data')
    czas = request.form.get('czas')
    opis = request.form.get('opis')
    file = request.files.get('file')
    cena = request.form.get('cena_biletu')

    old_concert = query_db("SELECT zdjecie FROM koncerty WHERE id = %s", (id,))

    if file and file.filename != '':
        delete_old_image(old_concert[0]['zdjecie'], 'koncerty')
        filename = save_image(file, 'koncerty')
        query_db("UPDATE koncerty SET id_artysty=%s, id_miejsca=%s, data=%s, czas=%s, opis=%s, zdjecie=%s, cena_biletu=%s WHERE id=%s", (id_artysty, id_miejsca, data, czas, opis, filename, cena, id), fetch=False)
    else:
        query_db("UPDATE koncerty SET id_artysty=%s, id_miejsca=%s, data=%s, czas=%s, opis=%s, cena_biletu=%s WHERE id=%s", (id_artysty, id_miejsca, data, czas, opis, cena, id), fetch=False)

    return jsonify({"status": "success"})

@app.route('/koncerty/usun/<int:id>', methods=['DELETE'])
def delete_concert(id):
    concert = query_db("SELECT zdjecie FROM koncerty WHERE id = %s", (id,))
    if concert:
        delete_old_image(concert[0]['zdjecie'], 'koncerty')
        query_db("DELETE FROM koncerty WHERE id = %s", (id,), fetch=False)
    return jsonify({"status": "success"})

@app.route('/artysci')
def artists():
    artists = query_db("SELECT a.id, a.nazwa, a.zdjecie, g.nazwa AS gatunek FROM artysci a JOIN gatunki g ON a.id_gatunku = g.id ORDER BY a.nazwa;")
    genres = query_db("SELECT id, nazwa FROM gatunki ORDER BY nazwa")
    return render_template('artists.html', artists=artists, genres=genres)

@app.route('/artysci/dodaj', methods=['POST'])
def add_artist():
    nazwa = request.form.get('nazwa')
    id_gatunku = request.form.get('id_gatunku')
    file = request.files.get('file')

    if file:
        filename = save_image(file, 'artysci')
    else:
        filename = 'default.png'

    query_db("INSERT INTO artysci (nazwa, id_gatunku, zdjecie) VALUES (%s, %s, %s)", (nazwa, id_gatunku, filename), fetch=False)
    return jsonify({"status": "success"})

@app.route('/artysci/<int:id>')
def get_artist(id):
    try:
        results = query_db("SELECT a.id, a.nazwa, g.nazwa AS gatunek, a.zdjecie FROM artysci a JOIN gatunki g ON a.id_gatunku = g.id WHERE a.id = %s", (id,))
        if not results:
            return jsonify({"status": "error", "message": "Nie znaleziono artysty"}), 404
        
        return jsonify(results[0])
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/artysci/edytuj', methods=['POST'])
def update_artist():
    id = request.form.get('id')
    nazwa = request.form.get('nazwa')
    id_gatunku = request.form.get('id_gatunku')
    file = request.files.get('file')

    old_artist = query_db("SELECT zdjecie FROM artysci WHERE id = %s", (id,))

    if file and file.filename != '':
        delete_old_image(old_artist[0]['zdjecie'], 'artysci')
        filename = save_image(file, 'artysci')
        query_db("UPDATE artysci SET nazwa=%s, id_gatunku=%s, zdjecie=%s WHERE id=%s", (nazwa, id_gatunku, filename, id), fetch=False)
    else:
        query_db("UPDATE artysci SET nazwa=%s, id_gatunku=%s WHERE id=%s", (nazwa, id_gatunku, id), fetch=False)

    return jsonify({"status": "success"})

@app.route('/artysci/usun/<int:id>', methods=['DELETE'])
def delete_artist(id):
    artist = query_db("SELECT zdjecie FROM artysci WHERE id = %s", (id,))
    if artist:
        delete_old_image(artist[0]['zdjecie'], 'artysci')
        query_db("DELETE FROM artysci WHERE id = %s", (id,), fetch=False)
    return jsonify({"status": "success"})

@app.route('/miejsca')
def venues():
    venues = query_db("SELECT * FROM miejsca ORDER BY nazwa;")
    return render_template('venues.html', venues=venues)

@app.route('/miejsca/dodaj', methods=['POST'])
def add_venue():
    nazwa = request.form.get('nazwa')
    miasto = request.form.get('miasto')
    adres = request.form.get('adres')
    pojemnosc = request.form.get('pojemnosc')
    file = request.files.get('file')
    if file:
        filename = save_image(file, 'miejsca')
    else:
        filename = 'default_venue.png'

    query_db("INSERT INTO miejsca (nazwa, miasto, adres, pojemnosc, zdjecie) VALUES (%s, %s, %s, %s, %s)", (nazwa, miasto, adres, pojemnosc, filename), fetch=False)
    
    return jsonify({"status": "success"})

@app.route('/miejsca/<int:id>')
def get_venue(id):
    try:
        results = query_db("SELECT id, nazwa, miasto, adres, pojemnosc, zdjecie FROM miejsca WHERE id = %s", (id,))
        if not results:
            return jsonify({"status": "error", "message": "Nie znaleziono miejsca"}), 404
        
        return jsonify(results[0])
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/miejsca/edytuj', methods=['POST'])
def update_venue():
    id = request.form.get('id')
    nazwa = request.form.get('nazwa')
    miasto = request.form.get('miasto')
    adres = request.form.get('adres')
    pojemnosc = request.form.get('pojemnosc')
    file = request.files.get('file')

    old_venue = query_db("SELECT zdjecie FROM miejsca WHERE id = %s", (id,))

    if file and file.filename != '':
        delete_old_image(old_venue[0]['zdjecie'], 'miejsca')
        filename = save_image(file, 'miejsca')
        query_db("UPDATE miejsca SET nazwa=%s, miasto=%s, adres=%s, pojemnosc=%s, zdjecie=%s WHERE id=%s", (nazwa, miasto, adres, pojemnosc, filename, id), fetch=False)
    else:
        query_db("UPDATE miejsca SET nazwa=%s, miasto=%s, adres=%s, pojemnosc=%s WHERE id=%s", (nazwa, miasto, adres, pojemnosc, id), fetch=False)

    return jsonify({"status": "success"})

@app.route('/miejsca/usun/<int:id>', methods=['DELETE'])
def delete_venue(id):
    venue = query_db("SELECT zdjecie FROM miejsca WHERE id = %s", (id,))
    if venue:
        delete_old_image(venue[0]['zdjecie'], 'miejsca')
        query_db("DELETE FROM miejsca WHERE id = %s", (id,), fetch=False)
    return jsonify({"status": "success"})

@app.route('/zamowienie/<int:id_koncertu>')
def order_page(id_koncertu):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    check = query_db("""
        SELECT m.pojemnosc, (SELECT COUNT(*) FROM bilety WHERE id_koncertu = %s) as sprzedane
        FROM koncerty k JOIN miejsca m ON k.id_miejsca = m.id
        WHERE k.id = %s
    """, (id_koncertu, id_koncertu))[0]

    if check['sprzedane'] >= check['pojemnosc']:
        flash('Przepraszamy, ten koncert został właśnie wyprzedany!', 'error')
        return redirect(url_for('concerts'))

    concert = query_db("SELECT k.*, a.nazwa as artysta, m.nazwa as miejsce FROM koncerty k JOIN artysci a ON k.id_artysty = a.id JOIN miejsca m ON k.id_miejsca = m.id WHERE k.id = %s", (id_koncertu,))

    return render_template('order.html', concert=concert[0])

@app.route('/kup-bilet', methods=['POST'])
def buy_ticket():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Zaloguj się!"}), 401

    id_uzytkownika = session.get('user_id')
    id_koncertu = request.form.get('id_koncertu')
    ilosc = int(request.form.get('ilosc', 1))

    with psycopg.connect(dbname="gigster_db", user="postgres", password="postgres", host="localhost", port="5432") as conn:
        try:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("SELECT cena_biletu FROM koncerty WHERE id = %s", (id_koncertu,))
                koncert = cur.fetchone()
                
                cur.execute("INSERT INTO zamowienia (id_uzytkownika) VALUES (%s) RETURNING id", (id_uzytkownika,))
                id_zamowienia = cur.fetchone()['id']

                for _ in range(ilosc):
                    cur.execute("""
                        INSERT INTO bilety (id_koncertu, id_zamowienia, cena) 
                        VALUES (%s, %s, %s)
                    """, (id_koncertu, id_zamowienia, koncert['cena_biletu']))

            conn.commit()
            flash("Udało się kupić bilety!")
            return jsonify({"status": "success", "message": f"Kupiono {ilosc} biletów!"})

        except Exception as e:
            conn.rollback()
            error_msg = str(e)
            if "Brak wolnych miejsc" in error_msg:
                return jsonify({"status": "error", "message": "Błąd: Niewystarczająca liczba wolnych miejsc (chciałeś kupić więcej niż jest dostępnych)."}), 400
            return jsonify({"status": "error", "message": "Błąd transakcji: " + error_msg}), 500
    
@app.route('/bilety')
def tickets():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    
    tickets = query_db("""
        SELECT b.id as bilet_id, k.opis as koncert, k.data, k.czas, 
               k.id as koncert_id, b.cena, z.czas_zlozenia
        FROM bilety b
        JOIN koncerty k ON b.id_koncertu = k.id
        JOIN zamowienia z ON b.id_zamowienia = z.id
        WHERE z.id_uzytkownika = %s
        ORDER BY z.czas_zlozenia DESC;
    """, (user_id,))

    return render_template('tickets.html', tickets=tickets)

@app.route('/rejestracja', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = 'user'
        if query_db("SELECT * FROM uzytkownicy WHERE nazwa = %s;", (username,)):
            flash('Użytkownik o podanej nazwie już istnieje.')
            return redirect(url_for('register'))
        
        try:
            hashed_pw = generate_password_hash(password)
            res = query_db(
                "INSERT INTO uzytkownicy (nazwa, haslo, rola) VALUES (%s, %s, %s) RETURNING id, rola;", 
                (username, hashed_pw, role)
            )
            
            new_user = res[0]

            session['logged_in'] = True
            session['username'] = username
            session['user_id'] = new_user['id']
            session['role'] = new_user['rola']

            flash('Rejestracja udana! Zostałeś automatycznie zalogowany.')
            return redirect(url_for('index'))

        except Exception as e:
            flash(f'Błąd rejestracji: {e}', 'error')
                
    return render_template('register.html')

@app.route('/logowanie', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = query_db("SELECT * FROM uzytkownicy WHERE nazwa = %s;", (username,))

        if user and check_password_hash(user[0]['haslo'], password):
            session['logged_in'] = True
            session['username'] = username
            session['user_id'] = user[0]['id']
            session['role'] = user[0]['rola']
            flash('Zalogowano pomyślnie!')
            return redirect(url_for('index'))
        else:
            flash('Nieprawidłowa nazwa użytkownika lub hasło.')
            return redirect(url_for('login'))

    return render_template('login.html')    

@app.route('/wylogowanie')
def logout():
    session.clear()
    flash('Wylogowano pomyślnie.', 'success')
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True)