# Next session — JJIT scraper plan mode

## Status
- Mac env działa (smoke test passed 14 May 2026)
- HF scraper + Opus extractor stabilne, cache hits potwierdzone
- Week 2 task: JJIT scraper plan mode

## Plan jutro
1. Chrome → https://justjoin.it → F12 (DevTools)
2. Network tab → filter Fetch/XHR → wpisz "offers" w Filter
3. Reload, znajdź request z listą ofert (response > kilkadziesiąt kB, nie tracker reklamowy)
4. Copy as cURL → wklej w rozmowie z Claude Desktop Project
5. Wracam do JJIT plan-mode prompt (sprawdź ostatnie wiadomości z Claude)
6. Review planu Claude Code → akceptacja → potem kod

## Decyzje już podjęte
- Portal order: HF ✓ → JJIT (next) → NFJ → Wellfound/YC
- LinkedIn: out
- Faza 4: human-in-the-loop, nie auto-submit
- Custom RAG od zera, potem LangChain comparison
- BaseScraper dopiero po 3 konkretach (rule of three, czyli po NFJ)

## Heads up
- JJIT to multi-company (różnica od HF single-company)
- ToS check przed scrapowaniem
- Plan mode obowiązkowy, nie skacz do kodu