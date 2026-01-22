BEGIN;

SET client_encoding = 'UTF8';

-- Gatunki muzyczne
CREATE TABLE gatunki (
    id SERIAL PRIMARY KEY,
    nazwa VARCHAR(30) NOT NULL
);

-- Obiekty koncertowe wraz z ich lokalizacją i limitami miejsc
CREATE TABLE miejsca (
    id SERIAL PRIMARY KEY,
    nazwa VARCHAR(50) NOT NULL,
    miasto VARCHAR(50),
    adres VARCHAR(100),
    pojemnosc INTEGER,
    zdjecie VARCHAR(30)
);

-- Dane kont użytkowników z podziałem na uprawnienia (user/admin)
CREATE TABLE uzytkownicy (
    id SERIAL PRIMARY KEY,
    nazwa VARCHAR(32) NOT NULL UNIQUE,
    haslo TEXT NOT NULL,
    rola VARCHAR(10) NOT NULL DEFAULT 'user' CHECK (rola IN ('user', 'admin'))
);

-- Wykonawcy muzyczni
CREATE TABLE artysci (
    id SERIAL PRIMARY KEY,
    nazwa VARCHAR(50) NOT NULL,
    id_gatunku INTEGER REFERENCES gatunki(id) ON DELETE CASCADE,
    zdjecie VARCHAR(30)
);

-- Wydarzenia koncertowe łączące artystów z miejscami i terminami
CREATE TABLE koncerty (
    id SERIAL PRIMARY KEY,
    id_artysty INTEGER NOT NULL REFERENCES artysci(id) ON DELETE CASCADE,
    id_miejsca INTEGER NOT NULL REFERENCES miejsca(id) ON DELETE CASCADE,
    data DATE,
    czas TIME,
    opis VARCHAR(200),
    zdjecie VARCHAR(50),
    cena_biletu NUMERIC(10, 2) DEFAULT 100.00 CHECK (cena_biletu >= 0)
);

-- Zamówienia składane przez użytkowników
CREATE TABLE zamowienia (
    id SERIAL PRIMARY KEY,
    id_uzytkownika INTEGER NOT NULL REFERENCES uzytkownicy(id) ON DELETE CASCADE,
    czas_zlozenia TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    kwota NUMERIC(10, 2)
);

-- Bilety powiązane z konkretnymi koncertami i zamówieniami
CREATE TABLE bilety (
    id SERIAL PRIMARY KEY,
    id_koncertu INTEGER NOT NULL REFERENCES koncerty(id) ON DELETE CASCADE,
    id_zamowienia INTEGER NOT NULL REFERENCES zamowienia(id) ON DELETE CASCADE,
    cena NUMERIC(10, 2)
);

-- Tabela do przechowywania historii zmian cen biletów
CREATE TABLE historia_cen (
    id SERIAL PRIMARY KEY,
    id_koncertu INTEGER NOT NULL REFERENCES koncerty(id) ON DELETE CASCADE,
    stara_cena NUMERIC(10,2),
    nowa_cena NUMERIC(10,2),
    data_zmiany TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Wstawianie przykładowych danych testowych
INSERT INTO gatunki (nazwa) VALUES 
('Hip-hop'), ('Pop'), ('Jazz');

INSERT INTO miejsca (nazwa, miasto, adres, pojemnosc, zdjecie) VALUES 
('TAURON Arena', 'Kraków', 'ul. Stanisława Lema 7', 15000, 'tauron_arena.png'),
('Spodek', 'Katowice', 'al. Korfantego 35', 11000, 'spodek.png'),
('PGE Narodowy', 'Warszawa', 'al. ks. J. Poniatowskiego 1', 58000, 'stadion_narodowy.png'),
('Hala Stulecia', 'Wrocław', 'ul. Wystawowa 1', 10000, 'hala_stulecia.png');

INSERT INTO uzytkownicy (nazwa, haslo, rola) VALUES 
('admin', 'scrypt:32768:8:1$aNAmLLlcobfSB5UN$3cfca6dbe293046ebb14c7289b032608197f6217dc9cc41b4e307b1ddab32720b20260ba9d48dd868319d338f6a261ebc33bfea583197302ad09a88ec63e986d', 'admin'),
('user', 'scrypt:32768:8:1$ATUqATZI2SdZb8OM$1d152d6fd536e87fd095941585cc6c125b790230812853a635754cc8b54c514570bed92ebaa0895a2178c6b0019e51b8955eece506b5244c4bfafe804094dbac', 'user');

INSERT INTO artysci (nazwa, id_gatunku, zdjecie) VALUES 
('Taco Hemingway', 1, 'taco.png'),
('Quebonafide', 1, 'quebo.png'),
('Olivia Rodrigo', 2, 'oliviarodrigo.jpg');

INSERT INTO koncerty (id_artysty, id_miejsca, data, czas, opis, zdjecie, cena_biletu) VALUES 
(1, 1, '2026-06-15', '20:00', '✝✝✝our', 'tttour.png', 200.00),
(2, 2, '2025-06-10', '19:30', 'AKT II - OSTATNI KONCERT', 'aktiiostatnikoncert.png', 250.00),
(3, 3, '2025-05-20', '19:00', 'GUTS WORLD TOUR', 'gutsworldtour.png', 300.00),
(1, 3, '2025-04-05', '21:00', '1-800-TOUR', '1800tour.png', 90.00),
(1, 4, '2022-07-12', '20:30', 'Pocztówka z Polski Tour', 'pocztowkatour.png', 220.00);

-- Zestawienie procentowe frekwencji na koncertach na podstawie sprzedanych biletów
CREATE OR REPLACE VIEW w_oblozenie_koncertow AS
SELECT 
    k.opis AS koncert, 
    a.nazwa AS artysta,
    m.nazwa AS miejsce,
    COUNT(b.id) AS zajete_miejsca,
    m.pojemnosc,
    ROUND((COUNT(b.id)::numeric / m.pojemnosc::numeric) * 100, 2) AS procent
FROM miejsca m
JOIN koncerty k ON m.id = k.id_miejsca
JOIN artysci a ON k.id_artysty = a.id
JOIN bilety b ON k.id = b.id_koncertu
GROUP BY koncert, artysta, miejsce, m.pojemnosc
HAVING COUNT(b.id) > 0
ORDER BY procent DESC;

-- Ranking finansowy i ilościowy popularności poszczególnych wykonawców
CREATE OR REPLACE VIEW w_popularnosc_artystow AS
SELECT 
    a.nazwa AS artysta, 
    COUNT(b.id) AS liczba_biletow,
    SUM(b.cena) AS kwota
FROM artysci a 
JOIN koncerty k ON a.id = k.id_artysty
JOIN bilety b ON k.id = b.id_koncertu
GROUP BY a.nazwa
ORDER BY liczba_biletow DESC;

-- Chronologiczne podsumowanie przychodów w ujęciu miesięcznym
CREATE OR REPLACE VIEW w_sprzedaz_miesieczna AS
SELECT 
    TO_CHAR(z.czas_zlozenia, 'YYYY-MM') AS miesiac,
    COUNT(b.id) AS liczba_biletow,
    SUM(b.cena) AS przychod
FROM zamowienia z
JOIN bilety b ON z.id = b.id_zamowienia
GROUP BY miesiac
ORDER BY miesiac DESC;

-- Analiza geograficzna sprzedaży biletów i średnich cen w miastach
CREATE OR REPLACE VIEW w_ranking_miast AS
SELECT 
    m.miasto,
    COUNT(b.id) AS liczba_sprzedanych_biletow,
    SUM(b.cena) AS laczny_przychod,
    ROUND(AVG(b.cena), 2) AS srednia_cena_biletu
FROM miejsca m
JOIN koncerty k ON m.id = k.id_miejsca
JOIN bilety b ON k.id = b.id_koncertu
GROUP BY m.miasto
ORDER BY laczny_przychod DESC;

-- Automatyczna synchronizacja łącznej kwoty zamówienia po dodaniu biletu
CREATE OR REPLACE FUNCTION aktualizuj_kwote_zamowienia()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE zamowienia 
    SET kwota = (SELECT SUM(cena) FROM bilety WHERE id_zamowienia = NEW.id_zamowienia)
    WHERE id = NEW.id_zamowienia;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_aktualizuj_kwote
AFTER INSERT OR UPDATE ON bilety
FOR EACH ROW
EXECUTE FUNCTION aktualizuj_kwote_zamowienia();

-- Weryfikacja dostępności wolnych miejsc przed finalizacją sprzedaży biletu
CREATE OR REPLACE FUNCTION sprawdz_limit_miejsc()
RETURNS TRIGGER AS $$
DECLARE
    v_zajete INTEGER;
    v_limit INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_zajete FROM bilety WHERE id_koncertu = NEW.id_koncertu;
    
    SELECT m.pojemnosc INTO v_limit 
    FROM miejsca m 
    JOIN koncerty k ON k.id_miejsca = m.id 
    WHERE k.id = NEW.id_koncertu;

    IF v_zajete >= v_limit THEN
        RAISE EXCEPTION 'Brak wolnych miejsc na ten koncert (Limit: %)', v_limit;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_limit_miejsc
BEFORE INSERT ON bilety
FOR EACH ROW
EXECUTE FUNCTION sprawdz_limit_miejsc();

-- Automatyczna archiwizacja zmian cen biletów w tabeli historycznej
CREATE OR REPLACE FUNCTION loguj_zmiane_ceny()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.cena_biletu <> NEW.cena_biletu THEN
        INSERT INTO historia_cen(id_koncertu, stara_cena, nowa_cena)
        VALUES (OLD.id, OLD.cena_biletu, NEW.cena_biletu);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_log_ceny
AFTER UPDATE ON koncerty
FOR EACH ROW
EXECUTE FUNCTION loguj_zmiane_ceny();

-- Sprawdzenie konfliktów w obiekcie koncertowym
CREATE OR REPLACE FUNCTION sprawdz_konfikt_miejsca()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM koncerty 
        WHERE id_miejsca = NEW.id_miejsca 
          AND data = NEW.data 
          AND id <> COALESCE(NEW.id, -1)
    ) THEN
        RAISE EXCEPTION 'Miejsce jest już zarezerwowane w tym dniu.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_brak_konfliktow
BEFORE INSERT OR UPDATE ON koncerty
FOR EACH ROW
EXECUTE FUNCTION sprawdz_konfikt_miejsca();

-- Walidacja daty koncertu
CREATE OR REPLACE FUNCTION waliduj_date_koncertu()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.data < CURRENT_DATE THEN
        RAISE EXCEPTION 'Koncert nie może odbywać się w przeszłości';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_walidacja_daty
BEFORE INSERT OR UPDATE ON koncerty
FOR EACH ROW
EXECUTE FUNCTION waliduj_date_koncertu();

COMMIT;