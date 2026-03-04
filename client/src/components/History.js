import DownloadIcon from "@mui/icons-material/Download";
import MenuIcon from "@mui/icons-material/Menu";
import {
  Box,
  createTheme,
  CssBaseline,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  ThemeProvider,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import Sidebar from "./Sidebar";

const History = ({ onLogout }) => {
  const [history, setHistory] = useState([]);
  const [darkMode, setDarkMode] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const theme = useMemo(
    () => createTheme({ palette: { mode: darkMode ? "dark" : "light" } }),
    [darkMode]
  );

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const token = localStorage.getItem("token");
        if (!token) return;

        const headers = {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        };

        const [cropRes, fertRes, yieldRes] = await Promise.all([
          fetch("http://127.0.0.1:5000/api/crop-predictions", { headers }),
          fetch("http://127.0.0.1:5000/api/fertilizer-recommendations", { headers }),
          fetch("http://127.0.0.1:5000/api/yield-predictions", { headers }),
        ]);

        const cropData = await cropRes.json();
        const fertData = await fertRes.json();
        const yieldData = await yieldRes.json();

        const all = [
          ...cropData.map((p) => ({
            date: p.createdAt,
            type: "Crop",
            crop: p.cropRecommendation || "Unknown",
            result: "Recommended Crop",
          })),
          ...fertData.map((p) => ({
            date: p.createdAt,
            type: "Fertilizer",
            crop: p.crop || "Unknown",
            result: p.fertilizerType || "Unknown",
          })),
          ...yieldData.map((p) => ({
            date: p.createdAt,
            type: "Yield",
            crop: p.crop || "Unknown",
            result: `${p.predictedYield || 0} tons/ha`,
          })),
        ];

        setHistory(all.sort((a, b) => new Date(b.date) - new Date(a.date)));
      } catch (err) {
        console.error("Failed to fetch history:", err);
      }
    };

    fetchHistory();
  }, []);

  const downloadCSV = () => {
    if (!history.length) return;

    const csvRows = [
      ["Date", "Type", "Crop", "Result"],
      ...history.map(({ date, type, crop, result }) => [
        new Date(date).toLocaleString(),
        type,
        crop,
        result,
      ]),
    ];

    const csvContent = csvRows
      .map((row) =>
        row.map((field) => `"${String(field).replace(/"/g, '""')}"`).join(",")
      )
      .join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "prediction_history.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Sidebar
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        isOpen={sidebarOpen}
        toggleSidebar={() => setSidebarOpen((prev) => !prev)}
      />

      {/* Top Bar */}
      <Box
        sx={{
          position: "fixed",
          top: 0,
          left: sidebarOpen ? "260px" : 0,
          right: 0,
          height: 56,
          backdropFilter: "blur(10px)",
          bgcolor: "rgba(255,255,255,0.15)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 2,
          zIndex: 1201,
          transition: "left 0.3s",
          boxShadow: 3,
        }}
      >
        <Box display="flex" alignItems="center">
          <IconButton onClick={() => setSidebarOpen((prev) => !prev)}>
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" sx={{ ml: 1 }}>
            Prediction History
          </Typography>
        </Box>

        <Box display="flex" alignItems="center" sx={{ cursor: "pointer" }} onClick={downloadCSV}>
          <Typography
            sx={{
              mr: 1,
              fontWeight: 500,
              fontSize: "16px",
              color: "#00695c",
              textDecoration: "underline",
            }}
          >
            Download here
          </Typography>
          <IconButton size="small">
            <DownloadIcon />
          </IconButton>
        </Box>
      </Box>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          pt: "80px",
          px: 4,
          minHeight: "100vh",
          ml: sidebarOpen ? "260px" : 0,
          transition: "margin 0.3s",
        }}
      >
        <Typography variant="h4" sx={{ mb: 2 }}>
          Full Prediction History
        </Typography>

        <Paper elevation={6} sx={{ overflow: "auto" }}>
          <Table>
            <TableHead sx={{ backgroundColor: "#43a047" }}>
              <TableRow>
                <TableCell sx={{ color: "#fff" }}>Date</TableCell>
                <TableCell sx={{ color: "#fff" }}>Type</TableCell>
                <TableCell sx={{ color: "#fff" }}>Crop</TableCell>
                <TableCell sx={{ color: "#fff" }}>Result</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {history.length > 0 ? (
                history.map((item, i) => (
                  <TableRow key={i}>
                    <TableCell>{new Date(item.date).toLocaleString()}</TableCell>
                    <TableCell>{item.type}</TableCell>
                    <TableCell>{item.crop}</TableCell>
                    <TableCell>{item.result}</TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4}>No history data available.</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Paper>
      </Box>
    </ThemeProvider>
  );
};

export default History;
