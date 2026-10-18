# Music Crow

Desktopowy odtwarzacz muzyki w Pythonie i PyQt6. Wyszukuje utwory w YouTube Music i SoundCloud, przechowuje playlisty lokalnie i obsługuje kolejkę, equalizer oraz płynne przejścia między utworami.

## Uruchomienie

Wymagany Python 3.10 lub nowszy oraz systemowa biblioteka **libmpv** (pakiet mpv/libmpv zależnie od dystrybucji).

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
bash start.sh
```

Skrypt korzysta kolejno z dostępnego interpretera `.venv`, `venv` lub systemowego `python3`. Wyszukiwanie uruchamia yt-dlp przez interpreter aplikacji. Połączenie internetowe jest wymagane do wyszukiwania i odtwarzania źródeł online. Dostępność utworów zależy od usług źródłowych.

Playlisty, okładki i ustawienia są zapisywane w `~/.config/music-crow/`. Integracja z klawiszami multimedialnymi przez MPRIS jest opcjonalna i wymaga `dbus-python`, PyGObject oraz sesji D-Bus. Kopie na Dysku Google można włączyć w ustawieniach po skonfigurowaniu logowania Google (instrukcja poniżej).

## Weryfikacja

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q core ui main.py
```

Testy sprawdzają zapis playlist (w tym przerwany zapis), kolejkę odtwarzania, zatrzymywanie obu instancji mpv, limit czasu procesu wyszukiwania oraz wyświetlanie miniatur. Nie wymagają dostępu do sieci.

## Rekomendacje na stronie głównej

Sekcja „Proponowane dla Ciebie” łączy utwory z playlist i historii z nowymi wynikami wyszukiwania ulubionych wykonawców. Kliknięcie propozycji odtwarza listę, a przycisk `+` pozwala dodać utwór do kolejki lub playlisty.

Historia nalicza jedno odsłuchanie na sesję po 30 sekundach rzeczywistego odtwarzania albo po połowie krótszego utworu (minimum 5 sekund). Pauza, ładowanie i przewijanie nie zwiększają licznika. Historia jest zapisywana lokalnie w `~/.config/music-crow/listening_history.json` i obejmuje maksymalnie 500 utworów. Nie obejmuje odsłuchań sprzed wprowadzenia tej funkcji.

Algorytm przyznaje 2 punkty za obecność na playliście, dodaje wagę zależną od liczby odsłuchań i zmniejsza wagę historii o połowę co 30 dni. Rekomendacje ograniczają liczbę utworów jednego wykonawcy do dwóch i pomijają aktualnie odtwarzany utwór. Odkrywanie nowości obejmuje najwyżej trzech wykonawców i korzysta z YouTube Music lub SoundCloud. Do usług trafiają zapytania z nazwą wykonawcy; historia pozostaje lokalna, chyba że włączysz jej uwzględnianie w kopii na własnym Dysku Google. Brak sieci nie blokuje propozycji z własnej biblioteki. Wyniki odkrywania są buforowane w pamięci przez 30 minut; przycisk „Odśwież” pozwala pobrać je ponownie.

### Dwie kolejki odtwarzania

Widok kolejki ma dwa panele z osobnym przewijaniem: „Z playlisty” i „Proponowane”. Lewy panel pokazuje utwory dodane do odtworzenia jako następne, a za nimi pozostałe utwory wybranej playlisty. Prawy zawiera dopasowaną kontynuację, która odtwarza się automatycznie po końcu lewej kolejki. Jeśli propozycje dotrą dopiero po końcu playlisty, odtwarzanie również ruszy automatycznie. Ręczne zatrzymanie blokuje takie wznowienie. Przy włączonym powtarzaniu playlisty propozycje czekają na wyłączenie powtarzania.

Przycisk „Następny →” przy propozycji przenosi utwór na początek lewej kolejki bez przerywania obecnego utworu. Można też przeciągnąć go na początek albo w wybrane miejsce pozostałej playlisty. Zmiana dotyczy bieżącej sesji i nie modyfikuje zapisanej playlisty. Kliknięcie karty odtwarza utwór od razu, a przycisk `✕` usuwa go z kolejki. Zmiana wybranej playlisty czyści poprzednią proponowaną kontynuację. Na stronie głównej propozycje znajdują się pod playlistami.

## Przygotowanie następnego utworu

Domyślnie aplikacja pobiera w tle audio **jednego następnego utworu** z faktycznej kolejki: uwzględnia „Następny”, zmianę kolejności, losowanie, powtarzanie i proponowaną kontynuację. Zmiana następnego utworu anuluje niepotrzebne pobieranie. Zwykłe odtwarzanie i płynne przejścia korzystają z gotowego pliku; w razie braku pliku odtwarzacz używa pierwotnego źródła online. Pierwszy utwór nadal może wymagać chwili na załadowanie, a wolne połączenie może nie pozwolić na przygotowanie kolejnego przed końcem bieżącego.

Stan przygotowania jest widoczny pod suwakiem odtwarzania. Funkcję można wyłączyć w **Ustawienia → Odtwarzanie i brzmienie → Przygotuj następny utwór**. Pliki trafiają do `~/.cache/music-crow/audio/`. Pamięć podręczna jest automatycznie przycinana do trzech ostatnich plików i około 200 MB, z ochroną aktualnie używanego i następnego pliku. Jeden plik ma limit 80 MB. Pobieranie wyprzedzające pomija transmisje na żywo i nagrania dłuższe niż 20 minut. Nie zapisuje utworów w playlistach ani w katalogu pobrań użytkownika.

## Język interfejsu i zapis propozycji

W **Ustawienia → Język → Język aplikacji** wybierz **Polski** lub **English**. Interfejs przełącza się od razu, bez restartu i przerywania odtwarzania. Wybór zapisuje się w `theme.json`; zmiana motywu go nie resetuje. Nazwy playlist, tytuły i wykonawcy pozostają w oryginalnej postaci.

W prawej kolejce „Proponowane” obok przycisku „Następny” znajduje się ikona **Dodaj do playlisty**. Wybierz istniejącą playlistę lub opcję **Utwórz nową playlistę…**. Zapisanie nie przerywa odtwarzania ani nie przenosi utworu z kolejki. Utwory już zapisane są oznaczone w menu i nie są dodawane ponownie. Ten sam wybór playlist jest dostępny przy propozycjach na stronie głównej oraz w wynikach wyszukiwania.

## Przeglądanie artysty / kanału

Kliknij nazwę wykonawcy pod utworem w wynikach, playliście, propozycjach lub dolnym pasku odtwarzania, aby otworzyć jego kanał w aplikacji. Widok pokazuje utwory z kanału YouTube lub profilu SoundCloud, po 30 pozycji; **Pokaż więcej** wczytuje kolejną partię. Można odtworzyć całą wczytaną listę, rozpocząć od wybranego utworu albo przez `+` dodać go do kolejki lub playlisty. **Wróć** przenosi na poprzedni ekran. Samo przeglądanie nie przerywa muzyki ani nie zmienia kolejki.

Nowe wyniki i importy zachowują adres kanału. Dla starszych zapisów aplikacja próbuje odczytać go z linku do utworu. Jeśli nie uda się ustalić kanału, pokazuje wyraźnie oznaczone wyniki wyszukiwania nazwy wykonawcy na tej samej platformie; mogą one obejmować nagrania z innych kanałów. Zawartość zależy od publicznej dostępności źródła, a kanał publikujący utwór nie zawsze należy do jego artysty. Ładowanie odbywa się w tle; przejście do innego wykonawcy anuluje poprzednie zapytanie.


## Dysk Google (Google Drive)

W **Ustawienia → Dysk Google** dostępne są logowanie przez Google, automatyczny zapis kopii, **Zapisz kopię teraz**, **Przywróć kopię…** i wylogowanie. Połączenia sieciowe i oczekiwanie na logowanie działają w tle; przycisk **Anuluj** zatrzymuje oczekiwanie. Sesja jest wznawiana po ponownym uruchomieniu aplikacji. Przy braku sieci nadal można korzystać z lokalnej biblioteki.

### Jednorazowa konfiguracja Google

Google wymaga zarejestrowanego klienta OAuth aplikacji. Repozytorium nie zawiera konfiguracji czy konta autora — trzeba raz przygotować własny projekt:

1. W [Google Cloud Console](https://console.cloud.google.com/) utwórz lub wybierz projekt i włącz **Google Drive API** w bibliotece API.
2. Skonfiguruj **Google Auth Platform / ekran zgody OAuth**: nazwę aplikacji i adres kontaktowy. Dla aplikacji w trybie testowym dodaj swój adres Google do użytkowników testowych.
3. W dostępie do danych dodaj zakres `https://www.googleapis.com/auth/drive.appdata`.
4. Utwórz **OAuth Client ID → Desktop app / Aplikacja komputerowa** i pobierz plik JSON klienta.
5. Uruchom aplikację przez `bash start.sh`. W ustawieniach kliknij **Wybierz konfigurację Google…**, wskaż pobrany JSON i wybierz **Zaloguj przez Google**. Dokończ zgodę w przeglądarce systemowej.
6. Na drugim komputerze skonfiguruj klienta z tego samego projektu Google i zaloguj się na to samo konto, a następnie wybierz **Przywróć kopię…**.

Instrukcje źródłowe Google: [OAuth dla aplikacji desktopowych](https://developers.google.com/identity/protocols/oauth2/native-app) oraz [dane aplikacji na Dysku](https://developers.google.com/workspace/drive/api/guides/appdata).

### Co jest zapisywane

Kopia zawiera playlisty, okładki oraz ustawienia języka, wyglądu i odtwarzania. Historię słuchania można dołączyć osobnym przełącznikiem (domyślnie wyłączony). Pliki audio, cache, dane logowania i konfiguracja OAuth nie są wysyłane. Limit jednej kopii to 40 MB, a pojedynczej okładki 5 MB.

Kopie trafiają do prywatnego obszaru **appDataFolder** na Dysku Google, a nie do widocznego folderu „Mój dysk”. Aplikacja prosi wyłącznie o zakres `drive.appdata`. Plik konfiguracji jest lokalnie zapisany jako `~/.config/music-crow/credentials.json`, a token sesji jako `google_token.json`, z uprawnieniami tylko dla właściciela. Wylogowanie usuwa lokalny token; nie kasuje danych z Dysku. Uprawnienia aplikacji można też odwołać w ustawieniach konta Google.

### Zapis i przywracanie

Automatyczny zapis działa po 3 sekundach od zmian oraz sprawdza stan co 5 minut. Identyczne dane nie są przesyłane ponownie. Każda instalacja aktualizuje własny plik kopii; kopie innych urządzeń pozostają osobne. To zapis kopii z ręcznym przywracaniem, bez automatycznego nadpisywania bibliotek między urządzeniami. Ręczny **Zapisz kopię teraz** działa również przy wyłączonym zapisie automatycznym.

Przywracanie najpierw pobiera i sprawdza całą kopię, następnie pokazuje liczbę playlist i utworów do potwierdzenia. Bieżące dane trafiają do `~/.config/music-crow/recovery/`. Ustawienia zostają przywrócone; playlisty są dołączane bez usuwania istniejących. Różniąca się playlista o tej samej nazwie otrzyma dopisek **(Google Drive)**, identyczna nie zostanie zdublowana. Historia jest łączona bez ponownego naliczania tych samych odsłuchań. Okładki dostają ścieżki właściwe dla bieżącego komputera. Zmiany są widoczne bez restartu i nie przerywają odtwarzania.

Testy protokołu OAuth/Drive używają kontrolowanych odpowiedzi i obejmują PKCE, weryfikację stanu logowania, anulowanie, zakres dostępu, pliki poszczególnych urządzeń, odtwarzanie danych i wycofanie zapisu po błędzie. Pełny test z prawdziwym kontem wymaga własnego pliku OAuth i zgody użytkownika w przeglądarce.
