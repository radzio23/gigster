BEGIN;

CREATE TABLE gatunki (
    id SERIAL PRIMARY KEY,
    nazwa VARCHAR(30) NOT NULL
);

CREATE TABLE miejsca (
    id SERIAL PRIMARY KEY,
    nazwa VARCHAR(50) NOT NULL,
    miasto VARCHAR(50),
    adres VARCHAR(100),
    pojemnosc INTEGER,
    zdjecie VARCHAR(30)
);

CREATE TABLE uzytkownicy (
    id SERIAL PRIMARY KEY,
    nazwa VARCHAR(32) NOT NULL UNIQUE,
    haslo TEXT NOT NULL,
    rola VARCHAR(5);
);

CREATE TABLE artysci (
    id SERIAL PRIMARY KEY,
    nazwa VARCHAR(50) NOT NULL,
    id_gatunku INTEGER REFERENCES gatunki(id) ON DELETE CASCADE,
    zdjecie VARCHAR(30)
);

CREATE TABLE koncerty (
    id SERIAL PRIMARY KEY,
    id_artysty INTEGER NOT NULL REFERENCES artysci(id) ON DELETE CASCADE,
    id_miejsca INTEGER NOT NULL REFERENCES miejsca(id) ON DELETE CASCADE,
    data DATE,
    czas TIME,
    opis VARCHAR(200),
    zdjecie VARCHAR(50),
    cena_biletu NUMERIC(10, 2) DEFAULT 100.00 CHECK (cena_biletu >= 0);
);

CREATE TABLE zamowienia (
    id SERIAL PRIMARY KEY,
    id_uzytkownika INTEGER NOT NULL REFERENCES uzytkownicy(id) ON DELETE CASCADE,
    czas_zlozenia TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    kwota NUMERIC(10, 2)
);

CREATE TABLE bilety (
    id SERIAL PRIMARY KEY,
    id_koncertu INTEGER NOT NULL REFERENCES koncerty(id) ON DELETE CASCADE,
    id_zamowienia INTEGER NOT NULL REFERENCES zamowienia(id) ON DELETE CASCADE,
    cena NUMERIC(10, 2),
);

CREATE TABLE historia_cen (
    id SERIAL PRIMARY KEY,
    id_koncertu INTEGER NOT NULL REFERENCES koncerty(id) ON DELETE CASCADE,
    stara_cena NUMERIC(10,2),
    nowa_cena NUMERIC(10,2),
    data_zmiany TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMIT;


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

CREATE OR REPLACE VIEW w_sprzedaz_miesieczna AS
SELECT 
    TO_CHAR(z.czas_zlozenia, 'YYYY-MM') AS miesiac,
    COUNT(b.id) AS liczba_biletow,
    SUM(b.cena) AS przychod
FROM zamowienia z
JOIN bilety b ON z.id = b.id_zamowienia
GROUP BY miesiac
ORDER BY miesiac DESC;

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
ORDER BY laczny_przychod DESC; -- Miasta zarabiające najwięcej na górze


------------
-- Funkcja triggera
CREATE OR REPLACE FUNCTION aktualizuj_kwote_zamowienia()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE zamowienia 
    SET kwota = (SELECT SUM(cena) FROM bilety WHERE id_zamowienia = NEW.id_zamowienia)
    WHERE id = NEW.id_zamowienia;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Sam trigger
CREATE TRIGGER trg_aktualizuj_kwote
AFTER INSERT OR UPDATE ON bilety
FOR EACH ROW
EXECUTE FUNCTION aktualizuj_kwote_zamowienia();


CREATE OR REPLACE FUNCTION sprawdz_limit_miejsc()
RETURNS TRIGGER AS $$
DECLARE
    v_zajete INTEGER;
    v_limit INTEGER;
BEGIN
    -- Liczymy zajęte miejsca na ten konkretny koncert
    SELECT COUNT(*) INTO v_zajete FROM bilety WHERE id_koncertu = NEW.id_koncertu;
    
    -- Pobieramy limit z tabeli miejsca
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