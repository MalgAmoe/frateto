import { useState, useEffect } from "react";
import { ChatSection } from "@llamaindex/chat-ui";
import { StarterQuestions } from "@llamaindex/chat-ui/widgets";
import { useChat } from "@ai-sdk/react";
import { Moon, Sun } from "lucide-react";

export default function FratetoChat() {
  const [isDark, setIsDark] = useState(true);

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
    api: "http://localhost:8000/api/chat",
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
          user_id: "1",
          session_id: body.id || "1",
        };

        return fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(customBody),
        });
      } catch (error) {
        console.error("Chat error:", error);
        throw error;
      }
    },
  });

  // EU Parliament starter questions
  const starterQuestions = [
    "What are the latest votes on climate change legislation?",
    "Show me voting patterns by political groups this month",
    "Which countries voted against recent AI regulation proposals?",
    "What are the most controversial votes in the last quarter?",
    "Analyze voting behavior on Ukraine-related resolutions",
    "Show me abstention patterns in agricultural policy votes",
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

      {/* Show starter questions when no messages, otherwise show chat */}
      {handler.messages.length === 0 ? (
        <div className="h-full flex flex-col items-center justify-center p-8">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-foreground mb-2">
              🏛️ Frateto
            </h1>
            <p className="text-muted-foreground text-lg">
              Your AI assistant for EU Parliament analysis
            </p>
            <p className="text-muted-foreground text-sm mt-2">
              Ask about votes, legislation, trends, and political behavior
            </p>
          </div>

          <StarterQuestions
            questions={starterQuestions}
            append={handler.append}
          />
        </div>
      ) : (
        <ChatSection handler={handler} className="h-full" />
      )}
    </div>
  );
}
