import { useState, useRef, useEffect } from "react";
import { FFmpeg } from "@ffmpeg/ffmpeg";
import { fetchFile, toBlobURL } from "@ffmpeg/util";
import { SUPPORTED_LANGUAGES, SOURCE_LANGUAGES } from "./constants/languages";
import { uploadAudio, getTaskStatus } from "./services/api";

function App() {
  const [loaded, setLoaded] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState("Starting Engine...");

  const [inputFile, setInputFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);

  const [sourceLang, setSourceLang] = useState("auto");
  const [targetLang, setTargetLang] = useState("en");
  const [context, setContext] = useState("");

  const [inputUrl, setInputUrl] = useState<string | null>(null);
  const [srtContent, setSrtContent] = useState<string | null>(null);
  const [subtitleUrl, setSubtitleUrl] = useState<string | null>(null);

  const ffmpegRef = useRef(new FFmpeg());

  useEffect(() => {
    loadEngine();
  }, []);

  const loadEngine = async () => {
    try {
      const baseURL = "https://unpkg.com/@ffmpeg/core@0.12.6/dist/esm";
      const ffmpeg = ffmpegRef.current;
      ffmpeg.on("progress", ({ progress }) => {
        if (progress >= 0 && progress <= 1)
          setProgress(Math.round(progress * 100));
      });
      await ffmpeg.load({
        coreURL: await toBlobURL(
          `${baseURL}/ffmpeg-core.js`,
          "text/javascript"
        ),
        wasmURL: await toBlobURL(
          `${baseURL}/ffmpeg-core.wasm`,
          "application/wasm"
        ),
      });
      setLoaded(true);
      setStatusText("Ready");
    } catch (error) {
      console.error(error);
      setStatusText("Engine failed to start. Please refresh the page.");
    }
  };

  const processToMp3 = async (file: File) => {
    setIsProcessing(true);
    setProgress(0);
    const ffmpeg = ffmpegRef.current;

    // Create filename
    const fileExtension = file.name.split(".").pop() || "tmp";
    const inputName = `input.${fileExtension}`;

    try {
      setStatusText(`Processing file ${fileExtension.toUpperCase()}...`);
      await ffmpeg.writeFile(inputName, await fetchFile(file));

      await ffmpeg.exec([
        "-i",
        inputName,
        "-vn", // No video
        "-map",
        "0:a:0", // First audio track
        "-ac",
        "1", // Mono
        "-ar",
        "16000", // 16kHz
        "-acodec",
        "libmp3lame",
        "-b:a",
        "32k",
        "output.mp3",
      ]);

      const data = await ffmpeg.readFile("output.mp3");
      const u8Arr = data as Uint8Array;
      const blob = new Blob([u8Arr.buffer as ArrayBuffer], {
        type: "audio/mp3",
      });
      const url = URL.createObjectURL(blob);

      setAudioBlob(blob);
      setAudioUrl(url);
      setStatusText("Ready to upload.");
    } catch (error) {
      console.error(error);
      setStatusText(
        "Error processing file. Video might not have audio or format not supported."
      );
    } finally {
      setIsProcessing(false);
      setProgress(100);
      try {
        await ffmpeg.deleteFile(inputName);
        await ffmpeg.deleteFile("output.mp3");
      } catch (e) {
        // Ignore
      }
    }
  };

  const handleFileChange = async (file: File | undefined) => {
    if (!file) return;
    setInputFile(file);
    setInputUrl(URL.createObjectURL(file));
    setAudioUrl(null);
    setAudioBlob(null);
    setSrtContent(null);
    setSubtitleUrl(null);
    setProgress(0);
    setIsProcessing(false);
    await processToMp3(file);
  };

  const srtToVtt = (srt: string) => {
    return "WEBVTT\n\n" + srt.replace(/(\d{2}:\d{2}:\d{2}),(\d{3})/g, "$1.$2");
  };

  const handleSendToServer = async () => {
    if (!audioBlob) return;

    setStatusText("⏳ Uploading & Translating...");

    try {
      const { task_id } = await uploadAudio(
        audioBlob,
        targetLang,
        sourceLang,
        context
      );

      setStatusText("⏳ Processing on Cloud (this may take a few minutes)...");

      // Polling loop
      const pollInterval = setInterval(async () => {
        try {
          const statusData = await getTaskStatus(task_id);

          if (statusData.state === "completed" && statusData.result) {
            clearInterval(pollInterval);
            const srt = statusData.result.srt_content;
            setSrtContent(srt);

            // Convert to VTT for preview
            const vttContent = srtToVtt(srt);
            const vttBlob = new Blob([vttContent], { type: "text/vtt" });
            setSubtitleUrl(URL.createObjectURL(vttBlob));

            setStatusText("Translation successful!");
            alert("Result is ready! Check preview below.");
          } else if (statusData.state === "failed") {
            clearInterval(pollInterval);
            throw new Error(statusData.error || "Task processing failed");
          } else {
            setStatusText(
              `Running: ${statusData.message || "Processing..."} (${
                statusData.progress || 0
              }%)`
            );
            setProgress(statusData.progress || 0);
          }
        } catch (e) {
          clearInterval(pollInterval);
          console.error(e);
          setStatusText("Error retrieving task status.");
        }
      }, 2000);
    } catch (error: any) {
      console.error(error);
      const msg = error.message || "Server connection error";
      setStatusText(`Error: ${msg}`);
      alert(msg);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans selection:bg-indigo-100 selection:text-indigo-800">
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute -top-[20%] -left-[10%] w-[50%] h-[50%] bg-indigo-200/30 rounded-full blur-3xl opacity-60 animate-pulse"></div>
        <div className="absolute top-[40%] -right-[10%] w-[40%] h-[40%] bg-purple-200/30 rounded-full blur-3xl opacity-60"></div>
      </div>

      <nav className="relative z-10 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="bg-indigo-600 p-2 rounded-lg shadow-lg shadow-indigo-200">
            <svg
              className="w-6 h-6 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"
              />
            </svg>
          </div>
          <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 to-purple-600">
            SubGen
          </span>
        </div>
        <div className="hidden sm:flex gap-6 text-sm font-medium text-slate-500">
          <a
            href="https://github.com/Datle-2003/video-subtitle-generator"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-indigo-600 transition-colors"
          >
            Github
          </a>
        </div>
      </nav>

      <main className="relative z-10 w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-16">
        <div className="text-center mb-12">
          <h1 className="text-4xl md:text-5xl font-extrabold text-slate-900 tracking-tight mb-4">
            Generate Video Subtitles
          </h1>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Automatically extract audio, translate, and generate subtitles for
            your video. Supports multiple languages.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
          <div className="bg-white rounded-2xl shadow-xl shadow-slate-200/50 overflow-hidden border border-slate-100 animate-slide-up">
            <div className="p-6 border-b border-slate-50 bg-slate-50/50">
              <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                <svg
                  className="w-5 h-5 text-indigo-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  ></path>
                </svg>
                Upload Video/Audio
              </h2>
            </div>

            <div className="p-8">
              {!loaded ? (
                <div className="flex flex-col items-center justify-center py-12 space-y-4">
                  <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
                  <p className="text-slate-500 font-medium animate-pulse">
                    Starting Processing Engine...
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  <label
                    className={`relative flex flex-col items-center justify-center w-full h-64 border-2 border-dashed rounded-xl cursor-pointer transition-all duration-300 group
                      ${
                        isProcessing
                          ? "bg-slate-50 border-slate-300 cursor-wait"
                          : "border-indigo-200 hover:border-indigo-500 hover:bg-indigo-50/30"
                      }
                      ${
                        inputFile && !isProcessing
                          ? "border-green-300 bg-green-50/30"
                          : ""
                      }
                    `}
                  >
                    <div className="flex flex-col items-center justify-center pt-5 pb-6 text-center px-4">
                      <div
                        className={`p-4 rounded-full mb-4 transition-transform group-hover:scale-110 duration-300 ${
                          inputFile
                            ? "bg-green-100 text-green-600"
                            : "bg-indigo-50 text-indigo-600"
                        }`}
                      >
                        {inputFile ? (
                          <svg
                            className="w-8 h-8"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M5 13l4 4L19 7"
                            />
                          </svg>
                        ) : (
                          <svg
                            className="w-8 h-8"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                            ></path>
                          </svg>
                        )}
                      </div>

                      {inputFile ? (
                        <>
                          <p className="text-base font-bold text-slate-700 break-all line-clamp-1 max-w-[90%]">
                            {inputFile.name}
                          </p>
                          <p className="text-sm text-slate-500 mt-1">
                            {(inputFile.size / 1024 / 1024).toFixed(2)} MB
                          </p>
                          <span className="mt-3 text-xs bg-white px-3 py-1 rounded-full border border-slate-200 text-slate-500 shadow-sm group-hover:border-indigo-300 transition-colors">
                            Click to change file
                          </span>
                        </>
                      ) : (
                        <>
                          <p className="mb-2 text-base text-slate-700 font-medium">
                            Click to select or drag & drop file here
                          </p>
                          <p className="text-xs text-slate-400">
                            Supports MP4, MKV, AVI, MP3, WAV
                          </p>
                        </>
                      )}
                    </div>
                    <input
                      type="file"
                      className="hidden"
                      accept="video/*,audio/*"
                      disabled={isProcessing}
                      onChange={(e) => handleFileChange(e.target.files?.[0])}
                    />

                    {isProcessing && (
                      <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-10 flex flex-col items-center justify-center rounded-xl">
                        <div className="w-3/4 max-w-xs space-y-3">
                          <div className="flex justify-between text-xs font-semibold text-slate-600 uppercase tracking-wider">
                            <span>Processing</span>
                            <span>{progress}%</span>
                          </div>
                          <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                            <div
                              className="bg-indigo-600 h-2 rounded-full transition-all duration-300 ease-out relative"
                              style={{ width: `${progress}%` }}
                            >
                              <div className="absolute inset-0 bg-white/30 animate-[shimmer_2s_infinite]"></div>
                            </div>
                          </div>
                          <p className="text-xs text-center text-slate-500">
                            {statusText}
                          </p>
                        </div>
                      </div>
                    )}
                  </label>
                </div>
              )}
            </div>

            <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex items-center gap-2 text-sm text-slate-600">
              <span
                className={`w-2 h-2 rounded-full ${
                  isProcessing ? "bg-amber-400 animate-pulse" : "bg-slate-300"
                }`}
              ></span>
              <span className="truncate flex-1">{statusText}</span>
            </div>
          </div>

          <div
            className="space-y-6 animate-slide-up"
            style={{ animationDelay: "0.1s" }}
          >
            <div className="bg-white rounded-2xl shadow-xl shadow-slate-200/50 p-6 border border-slate-100">
              <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
                <svg
                  className="w-5 h-5 text-indigo-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                Translation Config
              </h3>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    <span className="flex items-center gap-1.5">
                      <svg
                        className="w-4 h-4 text-slate-400"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                        />
                      </svg>
                      Audio Language (Source)
                    </span>
                  </label>
                  <select
                    value={sourceLang}
                    onChange={(e) => setSourceLang(e.target.value)}
                    className="block w-full rounded-lg border-slate-200 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm py-3 px-4 bg-slate-50 hover:bg-white transition-colors cursor-pointer"
                  >
                    {SOURCE_LANGUAGES.map((lang) => (
                      <option key={lang.code} value={lang.code}>
                        {lang.name}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-slate-400 mt-1">
                    Select the language spoken in the audio/video
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    <span className="flex items-center gap-1.5">
                      <svg
                        className="w-4 h-4 text-slate-400"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"
                        />
                      </svg>
                      Subtitle Language (Target)
                    </span>
                  </label>
                  <select
                    value={targetLang}
                    onChange={(e) => setTargetLang(e.target.value)}
                    className="block w-full rounded-lg border-slate-200 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm py-3 px-4 bg-slate-50 hover:bg-white transition-colors cursor-pointer"
                  >
                    {SUPPORTED_LANGUAGES.map((lang) => (
                      <option key={lang.code} value={lang.code}>
                        {lang.name}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-slate-400 mt-1">
                    The language for the generated subtitles
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Content Description / Context (Optional)
                  </label>
                  <textarea
                    value={context}
                    onChange={(e) => setContext(e.target.value)}
                    placeholder="Example: Action movie, Tutorial, For children..."
                    className="block w-full rounded-lg border-slate-200 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm py-3 px-4 bg-slate-50 hover:bg-white transition-colors"
                    rows={2}
                  />
                </div>

                <div className="pt-2">
                  <button
                    onClick={handleSendToServer}
                    disabled={!audioBlob}
                    className={`w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-bold text-white shadow-lg transition-all transform hover:-translate-y-0.5 active:translate-y-0
                          ${
                            audioBlob
                              ? "bg-indigo-600 hover:bg-indigo-700 hover:shadow-indigo-500/30"
                              : "bg-slate-300 cursor-not-allowed text-slate-500 shadow-none icon-disabled"
                          }
                        `}
                  >
                    {audioBlob ? (
                      <>
                        <span>Start Translating & Generating Subtitles</span>
                      </>
                    ) : (
                      <>
                        <span>Waiting for audio file...</span>
                      </>
                    )}
                  </button>
                  {!audioBlob && (
                    <p className="text-xs text-center text-slate-400 mt-2">
                      Please upload Video/Audio file first
                    </p>
                  )}
                </div>
              </div>
            </div>

            {(srtContent || audioUrl) && (
              <div className="bg-white rounded-2xl shadow-xl shadow-slate-200/50 p-6 border border-green-100 relative overflow-hidden animate-fade-in">
                <div className="absolute top-0 right-0 w-24 h-24 bg-green-100 rounded-bl-full -mr-8 -mt-8 opacity-50 pointer-events-none"></div>

                <h3 className="text-lg font-bold text-slate-800 mb-4 relative z-10 flex items-center gap-2">
                  <svg
                    className="w-5 h-5 text-green-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                    />
                  </svg>{" "}
                  Result & Preview
                </h3>

                <div className="space-y-4 relative z-10">
                  {subtitleUrl &&
                  inputUrl &&
                  inputFile?.type.startsWith("video/") ? (
                    <div className="bg-slate-900 rounded-xl overflow-hidden aspect-video relative group">
                      <video
                        controls
                        className="w-full h-full"
                        src={inputUrl}
                        crossOrigin="anonymous"
                      >
                        <track
                          key={subtitleUrl} // Force reload when URL changes
                          kind="subtitles"
                          label={targetLang.toUpperCase()}
                          srcLang={targetLang}
                          src={subtitleUrl}
                          default
                        />
                      </video>
                    </div>
                  ) : (
                    audioUrl && (
                      <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                        <p className="text-xs text-slate-500 mb-2">
                          Extracted Audio:
                        </p>
                        <audio controls src={audioUrl} className="w-full h-8" />
                      </div>
                    )
                  )}

                  <div className="flex gap-3 flex-wrap">
                    {srtContent && (
                      <a
                        href={URL.createObjectURL(
                          new Blob([srtContent], { type: "text/plain" })
                        )}
                        download={`${inputFile?.name.split(".")[0]}_sub.srt`}
                        className="flex-1 flex justify-center items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white py-2.5 px-4 rounded-lg text-sm font-bold transition-colors shadow-lg shadow-indigo-200"
                      >
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                          />
                        </svg>
                        Download SRT
                      </a>
                    )}

                    {audioUrl && (
                      <a
                        href={audioUrl}
                        download="extracted_audio.mp3"
                        className="flex-1 flex justify-center items-center gap-2 bg-white border border-slate-200 hover:border-indigo-300 text-slate-700 hover:text-indigo-600 py-2.5 px-4 rounded-lg text-sm font-medium transition-colors shadow-sm"
                      >
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
                          />
                        </svg>
                        Download MP3
                      </a>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      <footer className="w-full text-center py-6 text-slate-400 text-sm relative z-10"></footer>
    </div>
  );
}

export default App;
