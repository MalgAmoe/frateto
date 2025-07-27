import { useState, useEffect } from "react";
import { ChatSection } from "@llamaindex/chat-ui";
import { StarterQuestions } from "@llamaindex/chat-ui/widgets";
import { useChat } from "@ai-sdk/react";
import { Moon, Sun } from "lucide-react";

export default function FratetoChat() {
  const [isDark, setIsDark] = useState(true);
  const [showStarters, setShowStarters] = useState(true);
  const sessionData = window.FRATETO_SESSION;

  useEffect(() => {
    document.documentElement.classList.add("dark");
    const saved = localStorage.getItem("theme");
    if (saved === "light") {
      setIsDark(false);
      document.documentElement.classList.remove("dark");
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = !isDark;
    setIsDark(newTheme);

    if (newTheme) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  };

  const handler = useChat({
    api: `/api/chat`,
    fetch: async (url, options) => {
      try {
        if (!options?.body) {
          throw new Error("No request body provided");
        }

        const bodyString =
          typeof options.body === "string"
            ? options.body
            : new TextDecoder().decode(options.body as ArrayBuffer);

        const body = JSON.parse(bodyString);
        const lastMessage = body.messages[body.messages.length - 1];

        const customBody = {
          message: lastMessage.content,
          user_id: sessionData || "1",
          session_id: body.id || "1",
        };

        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(customBody),
        });

        // Create a custom readable stream that splits messages
        const reader = response.body?.getReader();
        const encoder = new TextEncoder();
        const decoder = new TextDecoder();

        let buffer = "";
        let messageCount = 0;

        const stream = new ReadableStream({
          async start(controller) {
            try {
              while (true) {
                const { done, value } = await reader!.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                  if (line.startsWith("0:")) {
                    // Check if this should be a new message
                    if (messageCount > 0) {
                      // End current message and start new one
                      controller.enqueue(
                        encoder.encode(
                          `d:{"finishReason":"continue","usage":{"promptTokens":5,"completionTokens":10}}\n`,
                        ),
                      );
                      controller.enqueue(encoder.encode(`0:""\n`)); // New message separator
                    }
                    controller.enqueue(encoder.encode(line + "\n"));
                    messageCount++;
                  } else {
                    controller.enqueue(encoder.encode(line + "\n"));
                  }
                }
              }
              controller.close();
            } catch (error) {
              controller.error(error);
            }
          },
        });

        return new Response(stream, {
          headers: response.headers,
        });
      } catch (error) {
        console.error("Chat error:", error);
        throw error;
      }
    },
  });

  // EU Parliament starter questions
  const starterQuestions = [
    "Which countries voted against recent AI regulation proposals?",
    "What are the most controversial votes in the last 6 month?",
    "Show me recent votes on climate and environmental protection",
    "Show voting patterns by country on Ukraine-related resolutions",
    "What digital rights and privacy laws are being debated?",
    "Compare voting behavior before and after 2024 elections",
    "Show me abstention patterns in agricultural policy votes",
    "Which parliamentary committees handle education and research funding?",
  ];

  return (
    <div className="h-screen relative">
      <button
        onClick={toggleTheme}
        className="absolute top-4 right-4 z-10 p-2 rounded-lg bg-background border border-border hover:bg-muted transition-colors"
        aria-label="Toggle theme"
      >
        {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>

      {showStarters && (
        <div className="absolute inset-0 z-20 bg-background flex flex-col items-center justify-center p-8">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-foreground mb-2">
              🏛️ Frateto Chat
            </h1>
            <p className="text-muted-foreground text-lg">
              Your AI assistant for EU Parliament analysis
            </p>
            <p className="text-muted-foreground text-sm mt-2">
              Ask about votes, legislation, trends, and political behavior
            </p>
          </div>

          <div className="w-full max-w-4xl">
            <StarterQuestions
              questions={starterQuestions}
              append={(value) => {
                setShowStarters(false);
                return handler.append(value);
              }}
            />
          </div>
          <button
            onClick={() => setShowStarters(false)}
            className="mt-6 p-2 rounded-lg bg-muted hover:bg-muted/80 transition-colors"
            aria-label="Close preset questions"
          >
            Close preset questions
          </button>
        </div>
      )}

      {/* Main chat interface */}
      <div className="h-full flex justify-center">
        <div className="w-full max-w-4xl">
          <ChatSection handler={handler} className="h-full" />
        </div>
      </div>
    </div>
  );
}
