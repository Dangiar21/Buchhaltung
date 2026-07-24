import os
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class Kunde(Base):
    __tablename__ = 'kunden'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    rechtsform = Column(String(100))
    beschreibung = Column(Text)
    partita_iva = Column(String(50))
    codice_fiscale = Column(String(50))
    regime_contabile = Column(String(100))
    liquidazione_iva = Column(String(100))
    adresse = Column(String(255))
    pec = Column(String(255))
    sdi = Column(String(50))
    iban = Column(String(100))

def init_db(db_path):
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()
