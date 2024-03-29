import "./globals.css";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { ProcessHistoryRoute } from "./routes/ProcessHistory";
import { ProcessEventRoute } from "./routes/ProcessEvent";

const container = document.getElementById("root");
const root = createRoot(container!);

const App = () => {
  return (
    <>
      <BrowserRouter>
        <Routes>
          <Route path="/run/:configId/:runId" element={<ProcessEventRoute />} />
          <Route path="/" element={<ProcessHistoryRoute />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </>
  );
};

root.render(<App />);
