import customtkinter as ctk
import speech_recognition as sr
import pyttsx3
import datetime
import wikipediaapi
import time
import threading
import sys
import os
import re
import queue

#UI Configuration 
ctk.set_appearance_mode("Dark")  
ctk.set_default_color_theme("dark-blue")

#TTS Configuration
TTS_RATE = 150        
TTS_VOLUME = 0.85     
TTS_VOICE_INDEX = None 
PREFERRED_VOICES = ["Samantha", "Zira", "Karen", "Tessa"] 

def print_available_voices(engine):
    """Helper to print all available voices to the console."""
    print("\n--- Available Voices ---")
    voices = engine.getProperty('voices')
    for idx, voice in enumerate(voices):
        print(f"Index: {idx} | Name: {voice.name} | ID: {voice.id}")
    print("------------------------\n")

#Command Processor
class CommandProcessor:
    """
    Handles parsing and execution of user commands.
    Maintains context for follow-up queries.
    """
    def __init__(self, app):
        self.app = app
        self.context = {"last_intent": None, "last_topic": None}
        self.commands = self._register_commands()
        
        # Initialize Wikipedia
        self.wiki_wiki = wikipediaapi.Wikipedia(
            language="en",
            extract_format=wikipediaapi.ExtractFormat.WIKI,
            user_agent="JarvisAssistant/1.0"
        )

    def _register_commands(self):
        return [
            {
                'keywords': ['time', 'current time', 'what time'],
                'handler': self.handle_time,
                'intent': 'time'
            },
            {
                'keywords': ['date', 'what day', 'todays date', 'current date'],
                'handler': self.handle_date,
                'intent': 'date'
            },
            {
                'keywords': ['search', 'tell me about', 'who is', 'what is', 'define'],
                'handler': self.handle_search,
                'intent': 'search'
            },
            {
                'keywords': ['play', 'song', 'music'],
                'handler': self.handle_play,
                'intent': 'play'
            },
            {
                'keywords': ['calculate', 'math', 'plus', 'minus', 'times', 'divided'],
                'handler': self.handle_math,
                'intent': 'math'
            },
            {
                'keywords': ['take a note', 'note this', 'write down'],
                'handler': self.handle_take_note,
                'intent': 'note_take'
            },
            {
                'keywords': ['read my notes', 'read notes', 'what are my notes'],
                'handler': self.handle_read_notes,
                'intent': 'note_read'
            },
            {
                'keywords': ['help', 'what can you do', 'capabilities'],
                'handler': self.handle_help,
                'intent': 'help'
            },
            {
                'keywords': ['stop', 'exit', 'quit', 'bye', 'goodbye'],
                'handler': self.handle_exit,
                'intent': 'exit'
            },
            {
                'keywords': ['and', 'also'],
                'handler': self.handle_context,
                'intent': 'context'
            }
        ]

    def process(self, text):
        text = text.lower().strip()
        if not text: return

        matched_cmd = None
        for cmd in self.commands:
            for keyword in cmd['keywords']:
                if keyword in text:
                    matched_cmd = cmd
                    break
            if matched_cmd: break
        
        if matched_cmd:
            self.app.set_status("Processing...")
            matched_cmd['handler'](text)
            if matched_cmd['intent'] != 'context':
                self.context['last_intent'] = matched_cmd['intent']
            self.app.set_status("Idle")
        else:
            self.app.speak("I didn't quite understand that. You can say 'help' to hear what I can do.")

    # --- Handlers ---

    def handle_time(self, text):
        time_str = datetime.datetime.now().strftime("%I:%M %p")
        self.app.speak(f"The time is {time_str}.")

    def handle_date(self, text):
        date_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
        self.app.speak(f"Today is {date_str}.")

    def handle_search(self, text):
        query = text
        for prefix in ['search for', 'search', 'tell me about', 'who is', 'what is', 'define']:
            if text.startswith(prefix):
                query = text.replace(prefix, "", 1).strip()
                break
        
        if not query:
            self.app.speak("What would you like me to search for?")
            return

        self.app.speak(f"Searching for {query}...")
        self.context['last_topic'] = query 
        
        try:
            page = self.wiki_wiki.page(query)
            if page.exists():
                # Clean up summary
                clean_summary = re.sub(r'\[.*?\]', '', page.summary) # Remove citations [1]
                clean_summary = re.sub(r'\(.*?\)', '', clean_summary) # Remove parens like (listen)
                
                #3-5 sentences
                sentences = re.split(r'(?<=[.!?]) +', clean_summary)
                short_summary = " ".join(sentences[:4]) # 4 sentences is a good balance
                
                # Limit total length
                if len(short_summary) > 600:
                    short_summary = short_summary[:600].rsplit(' ', 1)[0] + "..."
                
                self.app.speak(short_summary)
            else:
                self.app.speak(f"I couldn't find any specific information on {query}.")
        except Exception as e:
            print(f"Wiki Error: {e}")
            self.app.speak("I'm having trouble accessing Wikipedia right now.")

    def handle_play(self, text):
        song = text.replace("play", "").strip()
        if not song:
            self.app.speak("What should I play?")
            return
        
        self.app.speak(f"Playing {song} on YouTube.")
        try:
            import pywhatkit
            pywhatkit.playonyt(song)
        except Exception as e:
            print(f"Play Error: {e}")
            self.app.speak("I couldn't play that right now.")

    def handle_math(self, text):
        expression = text.replace("calculate", "").replace("what is", "").strip()
        expression = expression.replace("plus", "+").replace("minus", "-")
        expression = expression.replace("times", "*").replace("multiplied by", "*")
        expression = expression.replace("divided by", "/").replace("over", "/")
        
        safe_chars = "0123456789+-*/. ()"
        cleaned_expr = "".join([c for c in expression if c in safe_chars])
        
        if not cleaned_expr:
            self.app.speak("Please say a math problem.")
            return

        try:
            result = eval(cleaned_expr)
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            self.app.speak(f"The answer is {result}.")
        except:
            self.app.speak("I couldn't calculate that.")

    def handle_take_note(self, text):
        content = text
        for prefix in ['take a note', 'note this', 'write down']:
            if prefix in text:
                content = text.split(prefix, 1)[1].strip()
                break
        
        if not content:
            self.app.speak("What should I write down?")
            return

        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            with open("notes.txt", "a") as f:
                f.write(f"[{timestamp}] {content}\n")
            self.app.speak("I've saved that note for you.")
        except Exception as e:
            print(f"Note Error: {e}")
            self.app.speak("I couldn't save the note.")

    def handle_read_notes(self, text):
        if not os.path.exists("notes.txt"):
            self.app.speak("You don't have any notes yet.")
            return
        
        try:
            with open("notes.txt", "r") as f:
                lines = f.readlines()
            
            if not lines:
                self.app.speak("Your notes file is empty.")
                return

            recent_notes = lines[-3:]
            self.app.speak(f"Here are your last {len(recent_notes)} notes.")
            for note in recent_notes:
                if "]" in note:
                    content = note.split("]", 1)[1].strip()
                else:
                    content = note.strip()
                self.app.speak(content)
        except Exception as e:
            self.app.speak("I couldn't read your notes.")

    def handle_context(self, text):
        last_intent = self.context.get('last_intent')
        if last_intent == 'search':
            query = text.replace("and", "").replace("also", "").strip()
            if query:
                self.app.speak(f"Also searching for {query}...")
                self.handle_search(query)
            else:
                self.app.speak("What else would you like to know?")
        else:
            self.app.speak("I'm not sure what you're referring to.")

    def handle_help(self, text):
        help_msg = (
            "I can help you with:\n"
            "- Time and Date\n"
            "- Searching Wikipedia\n"
            "- Playing music on YouTube\n"
            "- Simple calculations\n"
            "- Taking and reading notes"
        )
        self.app.log_message("System", help_msg)
        self.app.speak("I can help with time, searching, playing music, math, and notes.")

    def handle_exit(self, text):
        self.app.speak("Goodbye!")
        self.app.after(1500, self.app.close_app)


# --- Main App ---
class VoiceAssistantApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window setup
        self.title("Jarvis AI")
        self.geometry("700x600")
        self.resizable(False, False)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) # Log area expands

        # Initialize core components
        self.is_listening = False
        self.should_stop = False
        self.engine = None 
        self.tts_queue = queue.Queue()

        self.processor = CommandProcessor(self)
        
        # UI Components
        self.create_widgets()
        
        # Start background thread for the assistant
        self.assistant_thread = threading.Thread(target=self.run_assistant_loop, daemon=True)
        self.assistant_thread.start()

    def create_widgets(self):
        # 1. Header Frame
        self.header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(25, 10))
        
        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="Jarvis AI", 
            font=ctk.CTkFont(family="Roboto", size=28, weight="bold")
        )
        self.title_label.pack(side="left")

        # 2. Conversation Log
        self.log_area = ctk.CTkTextbox(
            self, 
            width=640, 
            height=380, 
            corner_radius=15,
            font=ctk.CTkFont(family="Roboto", size=15),
            fg_color="#1a1a1a",
            text_color="#ecf0f1"
        )
        self.log_area.grid(row=1, column=0, padx=30, pady=10, sticky="nsew")
        self.log_area.configure(state="disabled") 

        # 3. Input Frame (Entry + Send)
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=2, column=0, sticky="ew", padx=30, pady=(0, 15))
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="Type a command...",
            height=45,
            corner_radius=10,
            font=ctk.CTkFont(size=14)
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", self.on_entry_submit)
        
        self.send_button = ctk.CTkButton(
            self.input_frame,
            text="➤",
            width=50,
            height=45,
            corner_radius=10,
            command=lambda: self.on_entry_submit(None)
        )
        self.send_button.grid(row=0, column=1)

        # 4. Toolbar (Listen, Help, Exit)
        self.toolbar_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.toolbar_frame.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 15))
        
        self.listen_button = ctk.CTkButton(
            self.toolbar_frame, 
            text="Listen", 
            command=self.toggle_listening,
            height=45,
            corner_radius=25,
            fg_color="#2ecc71", 
            hover_color="#27ae60",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.listen_button.pack(side="left", expand=True, fill="x", padx=(0, 10))

        self.help_button = ctk.CTkButton(
            self.toolbar_frame, 
            text="Help", 
            command=lambda: self.processor.handle_help(""),
            height=45,
            corner_radius=25,
            fg_color="#3498db",
            hover_color="#2980b9",
            font=ctk.CTkFont(size=15)
        )
        self.help_button.pack(side="left", expand=True, fill="x", padx=10)

        self.exit_button = ctk.CTkButton(
            self.toolbar_frame, 
            text="Exit", 
            command=self.close_app,
            height=45,
            corner_radius=25,
            fg_color="#e74c3c", 
            hover_color="#c0392b",
            font=ctk.CTkFont(size=15)
        )
        self.exit_button.pack(side="left", expand=True, fill="x", padx=(10, 0))

        # 5. Status Bar
        self.status_bar = ctk.CTkLabel(
            self,
            text="Status: Idle",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w"
        )
        self.status_bar.grid(row=4, column=0, sticky="ew", padx=35, pady=(0, 10))

    def set_status(self, status):
        color = "gray"
        if "Listening" in status: color = "#2ecc71"
        elif "Processing" in status: color = "#f1c40f"
        elif "Speaking" in status: color = "#3498db"
        
        self.status_bar.configure(text=f"Status: {status}", text_color=color)

    def log_message(self, sender, message):
        self.log_area.configure(state="normal")
        timestamp = datetime.datetime.now().strftime("%H:%M")
        
        if sender == "Jarvis":
            prefix = f"[{timestamp}] Jarvis: "
        elif sender == "System":
            prefix = f"[{timestamp}] System: "
        else:
            prefix = f"[{timestamp}] You: "

        self.log_area.insert("end", prefix + message + "\n\n")
        self.log_area.see("end")
        self.log_area.configure(state="disabled")

    def init_engine(self):
        try:
            self.engine = pyttsx3.init()
            
            voices = self.engine.getProperty('voices')
            selected_voice_id = voices[0].id 
            
            if isinstance(TTS_VOICE_INDEX, int) and 0 <= TTS_VOICE_INDEX < len(voices):
                selected_voice_id = voices[TTS_VOICE_INDEX].id
            elif TTS_VOICE_INDEX is None:
                found = False
                for name in PREFERRED_VOICES:
                    for voice in voices:
                        if name.lower() in voice.name.lower():
                            selected_voice_id = voice.id
                            found = True
                            break
                    if found: break

            self.engine.setProperty('voice', selected_voice_id)
            self.engine.setProperty('rate', TTS_RATE)
            self.engine.setProperty('volume', TTS_VOLUME)
            
        except Exception as e:
            self.log_message("System", f"Error initializing TTS: {e}")

    def speak(self, text):
        if not text: return
        self.tts_queue.put(text)

    def process_tts_queue(self):
        while not self.tts_queue.empty():
            try:
                text = self.tts_queue.get_nowait()
                
                self.after(0, self.log_message, "Jarvis", text)
                self.after(0, lambda: self.set_status("Speaking..."))
                
                if self.engine:
                    try:
                        self.engine.say(text)
                        self.engine.runAndWait()
                    except RuntimeError:
                        pass
                
                self.after(0, lambda: self.set_status("Idle"))
                time.sleep(0.2)
                self.tts_queue.task_done()
            except queue.Empty:
                break

    def listen_once(self):
        r = sr.Recognizer()
        with sr.Microphone() as source:
            self.after(0, lambda: self.set_status("Listening..."))
            
            try:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=5, phrase_time_limit=8)
                
                self.after(0, lambda: self.set_status("Processing..."))
                command = r.recognize_google(audio)
                self.after(0, self.log_message, "You", command)
                return command.lower()
                
            except sr.WaitTimeoutError:
                self.after(0, lambda: self.set_status("Idle"))
                return ""
            except sr.UnknownValueError:
                self.after(0, lambda: self.set_status("Idle"))
                self.speak("I didn't catch that.")
                return ""
            except Exception as e:
                self.after(0, lambda: self.set_status("Error"))
                self.after(0, self.log_message, "System", f"Mic Error: {e}")
                return ""

    def run_assistant_loop(self):
        self.init_engine()
        self.speak("Hello, I am ready to help.")
        self.after(0, lambda: self.set_status("Idle"))

        while not self.should_stop:
            # 1. Process TTS
            self.process_tts_queue()

            # 2. Listen if enabled
            if self.is_listening:
                command = self.listen_once()
                if command:
                    self.processor.process(command)
                
                self.is_listening = False 
                self.after(0, self.update_listen_button_state)
            else:
                time.sleep(0.1)

    def toggle_listening(self):
        if not self.is_listening:
            self.is_listening = True
            self.update_listen_button_state()
        else:
            self.is_listening = False
            self.update_listen_button_state()

    def update_listen_button_state(self):
        if self.is_listening:
            self.listen_button.configure(text="Listening...", fg_color="#e67e22", hover_color="#d35400")
            self.set_status("Listening...")
        else:
            self.listen_button.configure(text="Listen", fg_color="#2ecc71", hover_color="#27ae60")
            self.set_status("Idle")

    def on_entry_submit(self, event):
        text = self.entry.get()
        if text:
            self.entry.delete(0, "end")
            self.log_message("You", text)
            threading.Thread(target=self.processor.process, args=(text.lower(),)).start()

    def close_app(self):
        self.should_stop = True
        self.destroy()
        sys.exit()

if __name__ == "__main__":
    app = VoiceAssistantApp()
    app.mainloop() 