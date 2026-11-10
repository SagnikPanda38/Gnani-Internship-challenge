import { useEffect, useRef, useState } from "react";
import {
  ArrowRight, AudioLines, BookOpen, CheckCircle2, ChevronDown,
  CircleAlert, ExternalLink, FileText, GraduationCap, Languages,
  LoaderCircle, Mic, MicOff, Search, ShieldCheck, Sparkles, Wallet
} from "lucide-react";

const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const MAX_RECORD_SECONDS = 30; // Gnani's REST endpoint only accepts clips up to 30 s

// FastAPI sends `detail` as a string for our own errors and as a list for validation errors
const errorText = (data, fallback) => {
  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) return d.map((x) => x.msg).join(", ");
  return fallback;
};

// Safari records mp4, Chrome / Firefox record webm. Backend ffmpeg handles either.
const pickMime = () =>
  ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((t) => window.MediaRecorder?.isTypeSupported?.(t)) || "";

const money = (n) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);

export default function App() {
  const [language, setLanguage] = useState("hi-IN");
  const [education, setEducation] = useState("undergraduate");
  const [category, setCategory] = useState("general");
  const [income, setIncome] = useState("200000");
  const [stateName, setStateName] = useState("");
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState([]);
  const [notice, setNotice] = useState("");
  const [searchWarning, setSearchWarning] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(MAX_RECORD_SECONDS);
  const [info, setInfo] = useState("");
  const timerRef = useRef(null);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);

  useEffect(() => () => {
    clearInterval(timerRef.current);
    if (streamRef.current) streamRef.current.getTracks().forEach((track) => track.stop());
  }, []);

  useEffect(() => {
    if (hasSearched) document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [hasSearched]);

  async function startRecording() {
    setError("");
    setInfo("");
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError("Microphone recording is not supported in this browser. You can type your request instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = pickMime();
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || mime || "audio/webm" });
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        await transcribe(blob);
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
      setSecondsLeft(MAX_RECORD_SECONDS);
      clearInterval(timerRef.current);
      timerRef.current = setInterval(() => {
        setSecondsLeft((n) => {
          if (n <= 1) {
            clearInterval(timerRef.current);
            if (recorderRef.current && recorderRef.current.state !== "inactive") {
              recorderRef.current.stop();
              setRecording(false);
              setTranscribing(true);
            }
            return 0;
          }
          return n - 1;
        });
      }, 1000);
    } catch (e) {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      setRecording(false);
      setError(e.message || "Microphone permission was not granted.");
    }
  }

  function stopRecording() {
    clearInterval(timerRef.current);
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
      setRecording(false);
      setTranscribing(true);
    }
  }

  async function transcribe(blob) {
    setError("");
    setInfo("");
    try {
      const body = new FormData();
      body.append("audio", blob, blob.type.includes("mp4") ? "scheme-sathi.mp4" : "scheme-sathi.webm");
      const url = new URL(`${API}/api/transcribe`);
      url.searchParams.set("language_code", language);
      const response = await fetch(url, { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(errorText(data, "Speech transcription failed."));
      if (data.empty) {
        setInfo("We could not hear any speech in that recording. Try again a bit closer to the mic, or type your request.");
      } else {
        setQuery((old) => (old ? `${old} ${data.transcript}` : data.transcript));
      }
    } catch (e) {
      setError(e instanceof TypeError
        ? "Could not reach the backend. Check that it is running, or type your request instead."
        : e.message || "Could not transcribe audio. You can type your request instead.");
    } finally {
      setTranscribing(false);
    }
  }

  async function findScholarships(event) {
    event?.preventDefault();
    setLoading(true);
    setError("");
    setSearchWarning("");
    setHasSearched(false);
    try {
      const response = await fetch(`${API}/api/match`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          education_level: education,
          category,
          annual_income_inr: income === "" ? null : Number(income),
          state: stateName
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(errorText(data, "Could not search scholarships."));
      setMatches(data.matches || []);
      setNotice(data.notice || "");
      setSearchWarning(data.search_warning || "");
      setHasSearched(true);
    } catch (e) {
      setError(e instanceof TypeError
        ? "Could not reach the backend. Make sure the FastAPI server is running on " + API + "."
        : e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header className="nav">
        <a className="brand" href="#"><span className="brand-icon"><GraduationCap size={21}/></span>scheme<span>sathi</span></a>
        <div className="nav-right"><span className="privacy"><ShieldCheck size={15}/> Your details stay in this session</span>
          <label className="language"><Languages size={16}/><select value={language} onChange={(e) => setLanguage(e.target.value)}><option value="hi-IN">Hindi (हिन्दी)</option><option value="en-IN">English / Hinglish</option></select><ChevronDown size={13}/></label>
        </div>
      </header>

      <main className="container">
        <section className="hero">
          <div className="tag"><Sparkles size={14}/> STUDENT SCHOLARSHIP DISCOVERY</div>
          <h1>Find support for<br/><em>your next chapter.</em></h1>
          <p>Tell Scheme Sathi a little about yourself. Explore scholarship options in a simpler, more accessible way.</p>
        </section>

        <form className="layout" onSubmit={findScholarships}>
          <section className="panel form-panel">
            <div className="panel-heading"><div><small>01 / YOUR PROFILE</small><h2>Let's get to know you</h2></div><span className="step-icon"><GraduationCap size={20}/></span></div>
            <div className="field-grid">
              <label className="field"><span>Current education</span><select value={education} onChange={(e) => setEducation(e.target.value)}><option value="undergraduate">Undergraduate degree</option><option value="postgraduate">Postgraduate degree</option><option value="diploma">Diploma</option></select></label>
              <label className="field"><span>Category</span><select value={category} onChange={(e) => setCategory(e.target.value)}><option value="general">General</option><option value="obc">OBC</option><option value="sc">SC</option><option value="st">ST</option><option value="ews">EWS</option><option value="other">Other / Prefer not to say</option></select></label>
              <label className="field"><span>Annual family income (₹)</span><div className="input-icon"><Wallet size={16}/><input type="number" min="0" max="100000000" value={income} onChange={(e) => setIncome(e.target.value)} placeholder="e.g. 200000"/></div></label>
              <label className="field"><span>State / UT (optional)</span><input value={stateName} onChange={(e) => setStateName(e.target.value)} placeholder="e.g. West Bengal"/></label>
            </div>

            <div className="divider-label"><span/> TELL US IN YOUR OWN WORDS <span/></div>
            <p className="voice-hint">Speak in Hindi or Hinglish, or type your question below.</p>
            <div className="voice-row">
              <button className={`mic ${recording ? "recording" : ""}`} type="button" onClick={recording ? stopRecording : startRecording} disabled={transcribing}>
                {transcribing ? <LoaderCircle className="spin"/> : recording ? <MicOff/> : <Mic/>}
                {transcribing ? "Transcribing…" : recording ? "Stop recording" : "Speak your request"}
              </button>
              <span className="voice-caption"><AudioLines size={15}/> {recording ? `Listening, ${secondsLeft}s left. Tap stop when finished` : "Gnani Prisma speech recognition, up to 30 s"}</span>
            </div>
            <textarea rows="3" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Example: Mujhe engineering college ki fees ke liye scholarship chahiye…"/>
            {info && <div className="info"><AudioLines size={16}/>{info}</div>}
            {error && <div className="error"><CircleAlert size={16}/>{error}</div>}
            <button className="submit" type="submit" disabled={loading || transcribing}>{loading ? <><LoaderCircle className="spin"/> Finding scholarships…</> : <>Find scholarships <ArrowRight size={17}/></>}</button>
            <p className="privacy-note"><ShieldCheck size={14}/> No account needed. Avoid entering Aadhaar numbers or other sensitive identifiers.</p>
          </section>

          <aside className="side">
            <div className="side-card intro-card"><div className="illustration"><BookOpen size={27}/><Sparkles size={17}/></div><h3>One step closer to your goals.</h3><p>We compare your profile with a small catalogue of scholarship criteria and show potential options to explore.</p></div>
            <div className="side-card journey"><small>HOW IT WORKS</small><div className="journey-item"><b>01</b><span><strong>Share your profile</strong><small>Study level, category and income</small></span></div><div className="journey-item"><b>02</b><span><strong>Explore potential matches</strong><small>Transparent catalogue filters</small></span></div><div className="journey-item"><b>03</b><span><strong>Verify and apply</strong><small>Follow the official portal</small></span></div></div>
            <div className="side-note"><ShieldCheck size={17}/><span><b>Guidance, not a guarantee.</b><br/>Only the scheme authority can confirm eligibility and award decisions.</span></div>
          </aside>
        </form>

        {hasSearched && <section className="results" id="results">
        {searchWarning && (
          <div className="warning-message" role="status">
            <strong>Search and profile mismatch</strong>
            <p>{searchWarning}</p>
          </div>
        )}
          <div className="results-head"><div><small>02 / YOUR DISCOVERY</small><h2>Potential scholarship matches</h2><p>{matches.length ? `${matches.length} option${matches.length === 1 ? "" : "s"} to explore based on the details provided.` : "No catalogue matches found for these filters."}</p></div><span className="result-count">{matches.length} FOUND</span></div>
          {matches.length === 0 ? <div className="empty"><Search size={25}/><h3>No matches in our starter catalogue</h3><p>Try checking your profile details. This small prototype catalogue does not cover every scholarship.</p></div> :
            <div className="cards">{matches.map((scheme) => <article className="scheme-card" key={scheme.id}>
              <div className="scheme-top"><span className="scheme-symbol"><GraduationCap size={19}/></span><span className="potential"><CheckCircle2 size={14}/> Potential match</span></div>
              <h3>{scheme.short_name}</h3><p className="scheme-summary">{scheme.eligibility_summary}</p>
              <div className="meta"><span><Wallet size={14}/> {scheme.max_annual_income_inr ? `${scheme.income_rule_verified ? "Verified income ceiling" : "Unverified reference ceiling (not a filter)"}: ${money(scheme.max_annual_income_inr)}` : "Income: check official rules"}</span><span><FileText size={14}/> {scheme.documents.length} document types listed</span>{scheme.source_checked_on && <span><ShieldCheck size={14}/> Catalogue entry last checked {scheme.source_checked_on}</span>}</div>
              <div className="reason"><b>Why it appeared</b>{scheme.match_reasons.map((r, i) => <p key={i}>• {r}</p>)}</div>
              <div className="warning"><CircleAlert size={15}/><span>{scheme.warnings.join(" ") || "Check all current official conditions before applying."}</span></div>
              <a className="official-link" href={scheme.official_url} target="_blank" rel="noreferrer">Visit official scholarship portal <ExternalLink size={15}/></a>
            </article>)}</div>}
          <p className="notice">{notice}</p>
        </section>}

        <footer><span className="footer-brand">scheme<span>sathi</span></span><span>Built for accessible scholarship discovery</span><span>Prototype · Verify details with official authorities</span></footer>
      </main>
    </div>
  );
}
