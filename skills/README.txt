Bu klasordeki skill klasorleri uygulama tarafindan runtime'da diskten okunur.

Beklenen yapi:
- skills/<skill-slug>/meta.json
- skills/<skill-slug>/SKILL.md

Notlar:
- meta.json skill metadata'sini tutar.
- SKILL.md skill'in insan okunur talimatlarini ve orneklerini tutar.
- Varsayilan skill'ler silinirse API reset/uygulama bootstrap adiminda yeniden olusturulur.
