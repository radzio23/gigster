import uuid
import os
import psycopg
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

### FUNKCJE POMOCNICZE ###

db_url = os.getenv("DATABASE_URL")
# Uniwersalna funkcja do zapytań SQL
def query_db(query, params=None, fetch=True):
    with psycopg.connect(db_url, row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())    
            if fetch:
                return cur.fetchall()
            return None

# Usuwa stare zdjęcie z serwera
def delete_old_image(filename, category):
    if filename and filename != 'default.png':
        file_path = os.path.join('static/images/' + category, filename)
        if os.path.exists(file_path):
            os.remove(file_path)

# Zapisuje nowe zdjęcie z unikalną nazwą
def save_image(file, category):
    if file and file.filename != '':
        path = os.path.splitext(secure_filename(file.filename))
        unique_name = f"{path[0]}_{uuid.uuid4().hex[:4]}{path[1]}"
        file.save(os.path.join('static/images/' + category, unique_name))
        return unique_name
    return None

# Strona główna przekierowująca do listy koncertów
@app.route('/')
def index():
    return redirect(url_for('concerts'))

### MODUŁ ADMINISTRATOR ###

# Panel administratora - statystyki (widoki SQL) i zarządzanie użytkownikami.
@app.route('/admin/dashboard')
def dashboard():
    if session.get('role') != 'admin':
        flash('Brak uprawnień do panelu administratora.', 'error')
        return redirect(url_for('index'))

    return render_template('dashboard.html', 
                           sprzedaz=query_db("SELECT * FROM w_sprzedaz_miesieczna;"), 
                           oblozenie=query_db("SELECT * FROM w_oblozenie_koncertow;"), 
                           artysci=query_db("SELECT * FROM w_popularnosc_artystow;"),
                           miasta=query_db("SELECT * FROM w_ranking_miast;"),
                           uzytkownicy=query_db("SELECT id, nazwa, rola FROM uzytkownicy ORDER BY rola, nazwa"))

### MODUŁ UŻYTKOWNICY ###

# Pobieranie szczegółów jednego uzytkownika
@app.route('/uzytkownicy/<int:id>')
def get_user(id):
    res = query_db("SELECT * FROM uzytkownicy WHERE id = %s", (id,))
    if not res: return jsonify({"status": "error"}), 404
    return jsonify(res[0])

# Edycja użytkowników (tylko dla admina)
@app.route('/uzytkownicy/edytuj', methods=['POST'])
def edit_user():
    if session.get('role') != 'admin': return jsonify({"status": "error"}), 403
    
    user_id, nazwa, rola, haslo = request.form.get('id'), request.form.get('nazwa'), request.form.get('rola'), request.form.get('haslo')
    query_db("UPDATE uzytkownicy SET nazwa=%s, rola=%s WHERE id=%s", (nazwa, rola, user_id), fetch=False)
    
    if haslo and haslo.strip():
        query_db("UPDATE uzytkownicy SET haslo=%s WHERE id=%s", (generate_password_hash(haslo), user_id), fetch=False)

    flash(f'Dane użytkownika {nazwa} zostały zaktualizowane.', 'success')
    return jsonify({"status": "success"})

# Usuwanie użytkownika (tylko dla admina)
@app.route('/uzytkownicy/usun/<int:id>', methods=['POST'])
def delete_user(id):
    if session.get('role') != 'admin': return jsonify({"status": "error"}), 403
    if id == session.get('user_id'):
        flash('Nie możesz usunąć własnego konta!', 'error')
        return redirect(url_for('dashboard'))

    query_db("DELETE FROM uzytkownicy WHERE id = %s", (id,), fetch=False)
    flash('Użytkownik został pomyślnie usunięty.', 'info')
    return redirect(url_for('dashboard'))

### MODUŁ KONCERTY ###

# Lista koncertów z filtrowaniem
@app.route('/koncerty')
def concerts():
    artysta_id = request.args.get('artysta')
    miejsce_id = request.args.get('miejsce')
    gatunek_id = request.args.get('gatunek')
    miasto = request.args.get('miasto')

    query = "SELECT k.*, m.nazwa AS miejsce, m.miasto, a.nazwa AS artysta FROM koncerty k JOIN miejsca m ON m.id = k.id_miejsca JOIN artysci a ON a.id = k.id_artysty JOIN gatunki g ON a.id_gatunku = g.id"
    params, filters = [], []
    if artysta_id: 
        filters.append("k.id_artysty = %s"); 
        params.append(artysta_id)
    if miejsce_id: 
        filters.append("k.id_miejsca = %s"); 
        params.append(miejsce_id)
    if gatunek_id:
        filters.append("a.id_gatunku = %s")
        params.append(gatunek_id)
    if miasto:
        filters.append("m.miasto = %s")
        params.append(miasto)
    
    if filters: 
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY k.data DESC;"
    
    results = query_db(query, tuple(params))
    artists = query_db("SELECT id, nazwa FROM artysci ORDER BY nazwa")
    venues = query_db("SELECT id, nazwa FROM miejsca ORDER BY nazwa")
    genres = query_db("SELECT id, nazwa FROM gatunki ORDER BY nazwa")
    cities = query_db("SELECT DISTINCT miasto FROM miejsca ORDER BY miasto")

    return render_template('concerts.html', 
                           concerts=results, 
                           artists=artists, 
                           venues=venues,
                           genres=genres,
                           cities=cities)

# Dodawanie nowego koncertu
@app.route('/koncerty/dodaj', methods=['POST'])
def add_concert():
    try:
        f = request.form
        filename = save_image(request.files.get('file'), 'koncerty') or 'default.png'
        query_db("INSERT INTO koncerty (id_artysty, id_miejsca, data, czas, opis, zdjecie, cena_biletu) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                (f.get('id_artysty'), f.get('id_miejsca'), f.get('data'), f.get('czas'), f.get('opis'), filename, f.get('cena_biletu')), fetch=False)
        flash('Dodano nowy koncert do bazy.', 'success')
        return jsonify({"status": "success", "filename": filename})
    except Exception as e:        
        error_msg = str(e).split('\n')[0] 
        flash(f"Błąd podczas dodawania koncertu: {error_msg}", 'error')
        return jsonify({"status": "error"})

# Pobieranie szczegółów jednego koncertu
@app.route('/koncerty/<int:id>')
def get_concert(id):
    res = query_db("SELECT k.*, a.nazwa as artysta_nazwa, m.nazwa as miejsce_nazwa, (SELECT COUNT(*) FROM bilety b WHERE b.id_koncertu = k.id) as sprzedane, m.pojemnosc, m.miasto, m.adres FROM koncerty k JOIN artysci a ON k.id_artysty = a.id JOIN miejsca m ON k.id_miejsca = m.id WHERE k.id = %s", (id,))
    if not res: return jsonify({"status": "error"}), 404
    res[0]['data'], res[0]['czas'] = res[0]['data'].strftime("%d.%m.%Y"), str(res[0]['czas'])[:5]
    return jsonify(res[0])

# Edycja istniejącego koncertu
@app.route('/koncerty/edytuj', methods=['POST'])
def update_concert():
    try:
        f = request.form
        old_img = query_db("SELECT zdjecie FROM koncerty WHERE id = %s", (f.get('id'),))[0]['zdjecie']
        file = request.files.get('file')
        
        if file and file.filename != '':
            delete_old_image(old_img, 'koncerty')
            img = save_image(file, 'koncerty')
            query_db("UPDATE koncerty SET id_artysty=%s, id_miejsca=%s, data=%s, czas=%s, opis=%s, zdjecie=%s, cena_biletu=%s WHERE id=%s", 
                    (f.get('id_artysty'), f.get('id_miejsca'), f.get('data'), f.get('czas'), f.get('opis'), img, f.get('cena_biletu'), f.get('id')), fetch=False)
        else:
            query_db("UPDATE koncerty SET id_artysty=%s, id_miejsca=%s, data=%s, czas=%s, opis=%s, cena_biletu=%s WHERE id=%s", 
                    (f.get('id_artysty'), f.get('id_miejsca'), f.get('data'), f.get('czas'), f.get('opis'), f.get('cena_biletu'), f.get('id')), fetch=False)
        flash('Zmiany w koncercie zostały zapisane pomyślnie.', 'success')
        return jsonify({"status": "success"})
    except Exception as e:       
        error_msg = str(e).split('\n')[0] 
        flash(f"Błąd edycji koncertu: {error_msg}", 'error')
        return jsonify({"status": "error"})

# Usuwanie koncertu
@app.route('/koncerty/usun/<int:id>', methods=['DELETE'])
def delete_concert(id):
    res = query_db("SELECT zdjecie FROM koncerty WHERE id = %s", (id,))
    if res:
        delete_old_image(res[0]['zdjecie'], 'koncerty')
        query_db("DELETE FROM koncerty WHERE id = %s", (id,), fetch=False)
        flash('Koncert został pomyślnie usunięty.', 'info')
    return jsonify({"status": "success"})

### MODUŁ ARTYŚCI ###

# Lista artystów
@app.route('/artysci')
def artists():
    return render_template('artists.html', 
                           artists=query_db("SELECT a.*, g.nazwa AS gatunek FROM artysci a JOIN gatunki g ON a.id_gatunku = g.id ORDER BY a.nazwa;"),
                           genres=query_db("SELECT id, nazwa FROM gatunki ORDER BY nazwa"))

# Dodawanie nowego artysty
@app.route('/artysci/dodaj', methods=['POST'])
def add_artist():
    nazwa = request.form.get('nazwa')
    id_gatunku = request.form.get('id_gatunku')
    file = request.files.get('file')

    filename = save_image(file, 'artysci') or 'default.png'
    
    query_db("INSERT INTO artysci (nazwa, id_gatunku, zdjecie) VALUES (%s, %s, %s)", 
             (nazwa, id_gatunku, filename), fetch=False)
    flash(f'Artysta {nazwa} został pomyślnie dodany.', 'success')
    return jsonify({"status": "success"})

# Pobieranie danych jednego artysty
@app.route('/artysci/<int:id>')
def get_artist(id):
    res = query_db("SELECT a.id, a.nazwa, a.id_gatunku, a.zdjecie, g.nazwa AS gatunek_nazwa  FROM artysci a  JOIN gatunki g ON a.id_gatunku = g.id WHERE a.id = %s", (id,))
    if not res:
        return jsonify({"status": "error", "message": "Nie znaleziono artysty"}), 404
    return jsonify(res[0])

# Edycja danych artysty
@app.route('/artysci/edytuj', methods=['POST'])
def update_artist():
    id_artysty = request.form.get('id')
    nazwa = request.form.get('nazwa')
    id_gatunku = request.form.get('id_gatunku')
    file = request.files.get('file')

    old_img = query_db("SELECT zdjecie FROM artysci WHERE id = %s", (id_artysty,))
    
    if file and file.filename != '':
        delete_old_image(old_img[0]['zdjecie'], 'artysci')
        filename = save_image(file, 'artysci')
        query_db("UPDATE artysci SET nazwa=%s, id_gatunku=%s, zdjecie=%s WHERE id=%s", 
                 (nazwa, id_gatunku, filename, id_artysty), fetch=False)
    else:
        query_db("UPDATE artysci SET nazwa=%s, id_gatunku=%s WHERE id=%s", 
                 (nazwa, id_gatunku, id_artysty), fetch=False)
    flash(f'Zaktualizowano dane artysty {nazwa}.', 'success')
    return jsonify({"status": "success"})

# Usuwanie artysty
@app.route('/artysci/usun/<int:id>', methods=['DELETE'])
def delete_artist(id):
    artist = query_db("SELECT zdjecie FROM artysci WHERE id = %s", (id,))
    if artist:
        delete_old_image(artist[0]['zdjecie'], 'artysci')
        query_db("DELETE FROM artysci WHERE id = %s", (id,), fetch=False)
        flash('Artysta został usunięty z bazy.', 'info')
    return jsonify({"status": "success"})

### MODUŁ MIEJSCA ###

# Lista miejsc koncertowych
@app.route('/miejsca')
def venues():
    return render_template('venues.html', venues=query_db("SELECT * FROM miejsca ORDER BY nazwa;"))

# Dodawanie nowego miejsca
@app.route('/miejsca/dodaj', methods=['POST'])
def add_venue():
    nazwa = request.form.get('nazwa')
    miasto = request.form.get('miasto')
    adres = request.form.get('adres')
    pojemnosc = request.form.get('pojemnosc')
    file = request.files.get('file')

    filename = save_image(file, 'miejsca') or 'default.png'

    query_db("INSERT INTO miejsca (nazwa, miasto, adres, pojemnosc, zdjecie) VALUES (%s, %s, %s, %s, %s)", 
             (nazwa, miasto, adres, pojemnosc, filename), fetch=False)
    flash(f'Miejsce {nazwa} zostało pomyślnie dodane.', 'success')
    return jsonify({"status": "success"})

# Pobieranie danych jednego miejsca
@app.route('/miejsca/<int:id>')
def get_venue(id):
    res = query_db("SELECT * FROM miejsca WHERE id = %s", (id,))
    if not res:
        return jsonify({"status": "error", "message": "Nie znaleziono miejsca"}), 404
    return jsonify(res[0])

# Edycja danych miejsca
@app.route('/miejsca/edytuj', methods=['POST'])
def update_venue():
    id_miejsca = request.form.get('id')
    nazwa = request.form.get('nazwa')
    miasto = request.form.get('miasto')
    adres = request.form.get('adres')
    pojemnosc = request.form.get('pojemnosc')
    file = request.files.get('file')

    old_venue = query_db("SELECT zdjecie FROM miejsca WHERE id = %s", (id_miejsca,))

    if file and file.filename != '':
        delete_old_image(old_venue[0]['zdjecie'], 'miejsca')
        filename = save_image(file, 'miejsca')
        query_db("UPDATE miejsca SET nazwa=%s, miasto=%s, adres=%s, pojemnosc=%s, zdjecie=%s WHERE id=%s", 
                 (nazwa, miasto, adres, pojemnosc, filename, id_miejsca), fetch=False)
    else:
        query_db("UPDATE miejsca SET nazwa=%s, miasto=%s, adres=%s, pojemnosc=%s WHERE id=%s", 
                 (nazwa, miasto, adres, pojemnosc, id_miejsca), fetch=False)
    flash(f'Zaktualizowano dane obiektu {nazwa}.', 'success')
    return jsonify({"status": "success"})

# Usuwanie miejsca
@app.route('/miejsca/usun/<int:id>', methods=['DELETE'])
def delete_venue(id):
    venue = query_db("SELECT zdjecie FROM miejsca WHERE id = %s", (id,))
    if venue:
        delete_old_image(venue[0]['zdjecie'], 'miejsca')
        query_db("DELETE FROM miejsca WHERE id = %s", (id,), fetch=False)
        flash('Miejsce koncertowe zostało usunięte.', 'info')
    return jsonify({"status": "success"})

### MODUŁ ZAMÓWIENIA I BILETY ###

# Strona zamówienia biletów
@app.route('/zamowienie/<int:id_koncertu>')
def order_page(id_koncertu):
    if not session.get('logged_in'): 
        flash('Musisz się zalogować, aby kupić bilet.', 'info')
        return redirect(url_for('login'))
    
    check = query_db("SELECT m.pojemnosc, (SELECT COUNT(*) FROM bilety WHERE id_koncertu = %s) as sprzedane FROM koncerty k JOIN miejsca m ON k.id_miejsca = m.id WHERE k.id = %s", (id_koncertu, id_koncertu))[0]
    if check['sprzedane'] >= check['pojemnosc']:
        flash('Brak wolnych miejsc na ten koncert!', 'error')
        return redirect(url_for('concerts'))

    concert = query_db("SELECT k.*, a.nazwa as artysta, m.nazwa as miejsce FROM koncerty k JOIN artysci a ON k.id_artysty = a.id JOIN miejsca m ON k.id_miejsca = m.id WHERE k.id = %s", (id_koncertu,))
    return render_template('order.html', concert=concert[0])

# Proces zakupu biletów
@app.route('/kup-bilet', methods=['POST'])
def buy_ticket():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401

    uid, kid, ilosc = session.get('user_id'), request.form.get('id_koncertu'), int(request.form.get('ilosc', 1))

    with psycopg.connect(dbname="gigster_db", user="postgres", password="postgres", host="localhost", port="5432") as conn:
        try:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("SELECT cena_biletu FROM koncerty WHERE id = %s", (kid,))
                cena = cur.fetchone()['cena_biletu']
                
                cur.execute("INSERT INTO zamowienia (id_uzytkownika) VALUES (%s) RETURNING id", (uid,))
                zid = cur.fetchone()['id']

                for _ in range(ilosc):
                    cur.execute("INSERT INTO bilety (id_koncertu, id_zamowienia, cena) VALUES (%s, %s, %s)", (kid, zid, cena))
            conn.commit()
            flash(f'Sukces! Kupiono biletów: {ilosc}.', 'success')
            return jsonify({"status": "success", "message": f"Kupiono {ilosc} biletów!"})
        except Exception as e:
            conn.rollback()
            error_msg = str(e).split('\n')[0]
            flash(f"Błąd podczas zakupu: {error_msg}", 'error')
            return jsonify({"status": "error", "message": str(e)}), 400

# Lista biletów użytkownika
@app.route('/bilety')
def tickets():
    if not session.get('logged_in'): return redirect(url_for('login'))
    return render_template('tickets.html', tickets=query_db("SELECT b.*, k.id as koncert_id, k.opis as koncert, k.data, k.czas, z.czas_zlozenia FROM bilety b JOIN koncerty k ON b.id_koncertu = k.id JOIN zamowienia z ON b.id_zamowienia = z.id WHERE z.id_uzytkownika = %s ORDER BY z.czas_zlozenia DESC;", (session.get('user_id'),)))

### MODUŁ UŻYTKOWNICY I AUTORYZACJA ###

# Rejestracja nowego użytkownika
@app.route('/rejestracja', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user, pw = request.form['username'], request.form['password']
        if query_db("SELECT id FROM uzytkownicy WHERE nazwa = %s", (user,)):
            flash('Wybrana nazwa użytkownika jest już zajęta.', 'error')
            return redirect(url_for('register'))
        
        res = query_db("INSERT INTO uzytkownicy (nazwa, haslo, rola) VALUES (%s, %s, %s) RETURNING id, rola", 
                       (user, generate_password_hash(pw), 'user'))
        session.update({'logged_in': True, 'username': user, 'user_id': res[0]['id'], 'role': res[0]['rola']})
        flash(f'Witaj {user}! Twoje konto zostało utworzone.', 'success')
        return redirect(url_for('index'))
    return render_template('register.html')

# Logowanie użytkownika
@app.route('/logowanie', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = query_db("SELECT * FROM uzytkownicy WHERE nazwa = %s", (request.form['username'],))
        if user and check_password_hash(user[0]['haslo'], request.form['password']):
            session.update({'logged_in': True, 'username': user[0]['nazwa'], 'user_id': user[0]['id'], 'role': user[0]['rola']})
            flash(f'Witaj ponownie, {user[0]["nazwa"]}!', 'success')
            return redirect(url_for('index'))
        flash('Błędna nazwa użytkownika lub hasło.', 'error')
    return render_template('login.html')

# Wylogowanie użytkownika
@app.route('/wylogowanie')
def logout():
    session.clear()
    flash('Zostałeś pomyślnie wylogowany.', 'info')
    return redirect(url_for('index'))

# Uruchomienie aplikacji
if __name__ == "__main__":
    app.run(debug=True)
