import os
"""
database.py — Veritabanı şeması ve başlangıç verisi
Çalıştır: python database.py
"""

import sqlite3

DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "borsa.db")

HISSELER = {
    "GARAN": "Garanti BBVA",
    "THYAO": "Türk Hava Yolları",
    "KCHOL": "Koç Holding",
    "EREGL": "Ereğli Demir Çelik",
    "TUPRS": "Tüpraş",
    "BIMAS": "BİM Mağazaları",
    "ASELS": "Aselsan",
    "SAHOL": "Sabancı Holding",
    "SISE":  "Şişe Cam",
    "PETKM": "Petkim",
}


def veritabanini_olustur():
    conn = sqlite3.connect(DB_YOLU)
    c = conn.cursor()

    # 1. Takip edilen hisseler
    c.execute("""
        CREATE TABLE IF NOT EXISTS hisseler (
            hisse_kodu TEXT PRIMARY KEY NOT NULL,
            sirket_adi TEXT NOT NULL
        )
    """)

    # 2. Günlük OHLCV fiyat verileri
    c.execute("""
        CREATE TABLE IF NOT EXISTS gunluk_fiyatlar (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            hisse_kodu TEXT NOT NULL,
            tarih      DATE NOT NULL,
            acilis     REAL,
            kapanis    REAL,
            yuksek     REAL,
            dusuk      REAL,
            hacim      INTEGER,
            FOREIGN KEY (hisse_kodu) REFERENCES hisseler(hisse_kodu),
            UNIQUE(hisse_kodu, tarih)
        )
    """)

    # 3. KAP bildirimleri ve finans haberleri
    c.execute("""
        CREATE TABLE IF NOT EXISTS haberler (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            hisse_kodu  TEXT NOT NULL,
            tarih       DATETIME NOT NULL,
            baslik      TEXT,
            metin       TEXT NOT NULL,
            kaynak      TEXT,
            duygu_skoru REAL,
            FOREIGN KEY (hisse_kodu) REFERENCES hisseler(hisse_kodu)
        )
    """)

    # 4. X (Twitter) tweetleri
    # tweet_id UNIQUE → aynı tweet iki kez kaydedilmez
    c.execute("""
        CREATE TABLE IF NOT EXISTS tweetler (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tweet_id    TEXT UNIQUE NOT NULL,
            hisse_kodu  TEXT NOT NULL,
            tarih       DATETIME NOT NULL,
            metin       TEXT NOT NULL,
            duygu_skoru REAL,
            FOREIGN KEY (hisse_kodu) REFERENCES hisseler(hisse_kodu)
        )
    """)

    # 5. Günlük ortalama duygu skoru
    c.execute("""
        CREATE TABLE IF NOT EXISTS gunluk_duygu (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            hisse_kodu    TEXT NOT NULL,
            tarih         DATE NOT NULL,
            ortalama_skor REAL NOT NULL,
            kayit_sayisi  INTEGER NOT NULL,
            FOREIGN KEY (hisse_kodu) REFERENCES hisseler(hisse_kodu),
            UNIQUE(hisse_kodu, tarih)
        )
    """)

    # 6. Makro ekonomik gostergeler (BIST100, USDTRY, petrol, altin)
    c.execute("""
        CREATE TABLE IF NOT EXISTS makro_veriler (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih       DATE NOT NULL UNIQUE,
            bist100     REAL,
            usdtry      REAL,
            petrol      REAL,
            altin       REAL
        )
    """)

    # haberler duplikat temizligi: ayni (hisse_kodu, tarih, baslik) varsa eskisini sil
    c.execute("""
        DELETE FROM haberler
        WHERE id NOT IN (
            SELECT MIN(id) FROM haberler
            GROUP BY hisse_kodu, tarih, COALESCE(baslik, '')
        )
    """)
    # Unique index — hem yeni hem mevcut DB'de calisir
    c.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_haberler_unique
        ON haberler(hisse_kodu, tarih, COALESCE(baslik, ''))
    """)

    conn.commit()
    conn.close()
    print("Tablolar olusturuldu: hisseler, gunluk_fiyatlar, haberler, tweetler, gunluk_duygu, makro_veriler")


def hisseleri_ekle():
    conn = sqlite3.connect(DB_YOLU)
    c = conn.cursor()
    for kod, ad in HISSELER.items():
        c.execute(
            "INSERT OR IGNORE INTO hisseler (hisse_kodu, sirket_adi) VALUES (?, ?)",
            (kod, ad)
        )
    conn.commit()
    conn.close()
    print(f"{len(HISSELER)} hisse eklendi/kontrol edildi.")


if __name__ == "__main__":
    veritabanini_olustur()
    hisseleri_ekle()
    print(f"\nVeritabani hazir: {DB_YOLU}")
