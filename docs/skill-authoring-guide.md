# Skill Authoring Guide

Bu rehber, proje icindeki disk tabanli skill'leri nasil tanimlayacaginizi ve runtime'da neyin gercekten calistigini ozetler.

## Dizin Yapisi

Her skill su klasor yapisinda tutulur:

```text
skills/<skill-slug>/
  meta.json
  SKILL.md
```

Opsiyonel klasorler:

- `prompts/`
- `assets/`
- `examples/`

Beklenmeyen dosya veya klasorler runtime tarafinda yok sayilir. Symlink ve root disina tasan path'ler reddedilir.

## Zorunlu Alanlar

`meta.json` icinde tipik alanlar:

```json
{
  "schema_version": 1,
  "slug": "brand-voice-rewrite",
  "name": "Brand Voice Rewrite",
  "description": "Mevcut urun anlatimini daha kontrollu hale getirir.",
  "when_to_use": "Marka tonu daginiksa kullan.",
  "applies_to": ["chat", "rewrite", "batch"],
  "allowed_tools": ["get_product_details", "validate_rewrite"],
  "prompt_layers": [
    {
      "type": "inline",
      "label": "Brand Voice Constraints",
      "content": "Marka tonu sakin ve guven verici olmali."
    }
  ],
  "tags": ["brand", "rewrite"],
  "priority": 30,
  "status": "active"
}
```

## `SKILL.md` Ne Ise Yarar

`SKILL.md`, skill'in ana talimat metnidir. Runtime prompt'a dogrudan eklenir.

Burada su tip icerikler olmali:

- skill'in hedefi
- hangi durumda devreye girmesi gerektigi
- hangi sinirlarin korunacagi
- varsa negatif kurallar

## `prompt_layers`

Iki tip desteklenir:

- `inline`: dogrudan metin ekler
- `prompt_reference`: mevcut `prompt_store` anahtarlarindan birini referans alir

Ornek:

```json
{
  "type": "prompt_reference",
  "label": "Rewrite System",
  "prompt_key": "rewrite_agent_system"
}
```

## `allowed_tools`

`allowed_tools`, skill'in istedigi tool listesidir. Runtime'da flow'un gercek tool seti ile kesistirilir.

Bugunku davranis:

- `chat`: tool kisiti aktif olarak uygulanir
- `rewrite`: agentic tam-urun rewrite'ta uygulanir
- `batch`: su an ana etki prompt enjeksiyonudur; tool kisiti debug/preview seviyesinde gorunur ama batch runtime field-by-field calisir

Bos birakilirsa skill tool kisiti uygulamaz.

## `applies_to`

Skill'in nerede secilebilecegini belirler:

- `chat`
- `rewrite`
- `batch`

Bir flow burada yoksa skill o flow'da secilemez.

## Runtime'da Ne Olur

### Chat

- Chat header veya websocket komutuyla skill secilir
- `SKILL.md` ve resolve edilen layer'lar chat system prompt'una eklenir
- `allowed_tools` chat tool setini filtreler

### Rewrite

- `skill_slug` endpoint'e gonderilir
- skill prompt'u rewrite system prompt'una eklenir
- agentic rewrite aciksa tool seti filtrelenir

### Batch

- `config.skill_slug` ile secilir
- batch kisitlariyla birlikte her field rewrite/translation istegine enjekte edilir

## Skill Studio

Skill Studio uzerinden:

- skill listesi gorulur
- metadata duzenlenir
- `SKILL.md` duzenlenir
- `allowed_tools` secilir
- `applies_to` secilir
- preview ve validation calistirilir
- uygun bir skill dashboard chat'ine uygulanip test edilebilir

## Iyi Bir Skill Yazmak Icin

- Skill'i tek bir davranis eksenine odaklayin
- Genel AI talimati degil, operasyonel sinirlar yazin
- Urun verisine sadakat ve claim uydurmama kurali acik olsun
- `allowed_tools` listesini genis degil dar tutun
- `applies_to` alanini sadece gercekten desteklenen flow'larla sinirlayin

## Kontrol Listesi

Bir skill kaydetmeden once sunlari kontrol edin:

- `slug` kucuk harf ve tire formatinda mi
- `status` dogru mu (`active`, `draft`, `disabled`)
- `applies_to` dogru flow'lari iceriyor mu
- `allowed_tools` sadece mevcut tool isimlerinden mi olusuyor
- preview ciktisi beklediginiz ton ve sinirlari veriyor mu
- batch icin yaziyorsaniz tool kisiti degil prompt davranisinin esas oldugunu biliyor musunuz
