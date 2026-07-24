from pydantic import BaseModel, Field, field_validator
import re

class ClientDataValidator(BaseModel):
    Kundenname: str = Field(..., min_length=1, description="Firmenname darf nicht leer sein.")
    Rechtsform: str = ""
    Beschreibung: str = ""
    Partita_IVA: str = ""
    Codice_Fiscale: str = ""
    Regime_Contabile: str = ""
    Liquidazione_IVA: str = ""
    Adresse: str = ""
    PEC: str = ""
    SDI: str = ""
    IBAN: str = ""

    @field_validator('Partita_IVA')
    @classmethod
    def validate_partita_iva(cls, v: str) -> str:
        v = v.strip()
        if v and not re.match(r'^\d{11}$', v):
            raise ValueError("Partita IVA muss exakt aus 11 Ziffern bestehen.")
        return v

    @field_validator('PEC')
    @classmethod
    def validate_pec(cls, v: str) -> str:
        v = v.strip()
        if v and not re.match(r'^.+@.+\..+$', v):
            raise ValueError("PEC muss eine gültige E-Mail-Adresse sein (mit '@' und Punkt).")
        return v

    @field_validator('IBAN')
    @classmethod
    def validate_iban(cls, v: str) -> str:
        v = v.strip().replace(" ", "").upper()
        if v and not re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$', v):
            raise ValueError("IBAN hat ein ungültiges Format (z.B. IT12...).")
        return v
