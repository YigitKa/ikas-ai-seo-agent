Bu klasordeki prompt dosyalari uygulama tarafindan her AI isteginde yeniden okunur.

Ozellestirebilecegin dosyalar:
- description_rewrite.system.txt
- description_rewrite.user.txt
- translation_en.system.txt
- translation_en.user.txt

Kullanilabilir degiskenler:
- description_rewrite.user.txt: {{name}}, {{description}}, {{category}}, {{keywords}}
- translation_en.user.txt: {{name}}, {{description}}, {{category}}

Notlar:
- JSON orneklerini normal sekilde yazabilirsin. Cift kacis gerekmiyor.
- Degiskenler icin sadece {{degisken_adi}} formatini kullan.
- Dosya bos birakilirsa uygulama varsayilan prompta geri doner.
