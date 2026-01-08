export interface TaskStatus {
    state: "pending" | "processing" | "completed" | "failed";
    progress: number;
    message?: string;
    result?: {
        srt_content: string;
        filename: string;
    };
    error?: string;
}

// Use environment variable for production, fallback to localhost for development
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const uploadAudio = async (
    audioBlob: Blob,
    targetLang: string,
    sourceLang: string,
    context?: string
): Promise<{ task_id: string; message: string }> => {
    const formData = new FormData();
    formData.append("file", audioBlob, "audio.mp3");
    formData.append("target_lang", targetLang);
    formData.append("source_lang", sourceLang);
    if (context) {
        formData.append("context", context);
    }

    const response = await fetch(`${API_BASE_URL}/generate-subtitle`, {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        let errorMessage = "Failed to upload audio";
        try {
            const errorData = await response.json();
            // FastAPI returns 'detail' for HTTP exceptions, our custom errors might use 'error'
            errorMessage = errorData.detail || errorData.error || errorMessage;
        } catch (e) {
            // If response is not JSON, stick to default
        }
        throw new Error(errorMessage);
    }

    return response.json();
};

export const getTaskStatus = async (taskId: string): Promise<TaskStatus> => {
    const response = await fetch(`${API_BASE_URL}/status/${taskId}`);

    if (!response.ok) {
        throw new Error("Failed to get task status");
    }

    return response.json();
};
