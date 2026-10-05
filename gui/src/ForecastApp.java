import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableCellRenderer;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.awt.event.MouseAdapter;
import java.awt.event.MouseEvent;
import java.awt.geom.Path2D;
import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.*;
import java.util.List;

/**
 * Графический интерфейс для прогноза потребления ОЭС Северо-Запада моделью Chronos-2.
 * Запускает model/predict.py через виртуальное окружение проекта и показывает результат:
 * график с коридором 10–90 %, почасовую таблицу, сводку и журнал.
 */
public class ForecastApp extends JFrame {
    // палитра
    static final Color BG = new Color(0xF5F5F7), CARD = Color.WHITE, INK = new Color(0x1D1D1F),
            INK2 = new Color(0x6E6E73), ACCENT = new Color(0x0071E3), BAND = new Color(0x0071E3, false),
            GRID = new Color(0xE5E5EA), GOOD = new Color(0x1E9E5A);
    static final String[][] MODELS = {
            {"chronos-lora", "Chronos-2, дообучение LoRA (лучшая, 0,84 %)"},
            {"chronos-zs", "Chronos-2 без дообучения (0,97 %)"}};

    record Row(int hour, double fc, double p10, double p90, Double actual, Double temp) {}

    final File root;
    final JSpinner dateSpin = new JSpinner(new SpinnerDateModel());
    final JComboBox<String> modelBox = new JComboBox<>(Arrays.stream(MODELS).map(m -> m[1]).toArray(String[]::new));
    final JCheckBox update = new JCheckBox("Обновлять данные с сайтов (СО ЕЭС, Open-Meteo)", true);
    final JButton tomorrowBtn = new JButton("Прогноз на завтра"), runBtn = new JButton("Сделать прогноз"),
            saveBtn = new JButton("Сохранить CSV");
    final JProgressBar progress = new JProgressBar();
    final JLabel status = new JLabel("Выберите дату и нажмите «Сделать прогноз»");
    final Map<String, JLabel> stats = new LinkedHashMap<>();
    final ChartPanel chart = new ChartPanel();
    final DefaultTableModel tableModel = new DefaultTableModel(
            new String[]{"Час", "Прогноз, МВт", "10 %", "90 %", "Факт, МВт", "Ошибка, %", "Темп., °C"}, 0) {
        @Override public boolean isCellEditable(int r, int c) { return false; }
    };
    final JTextArea logArea = new JTextArea();
    List<Row> rows = new ArrayList<>();
    Map<String, String> meta = new HashMap<>();

    public ForecastApp(File root) {
        super("Прогноз потребления — ОЭС Северо-Запада");
        this.root = root;
        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setMinimumSize(new Dimension(980, 680));
        getContentPane().setBackground(BG);
        setLayout(new BorderLayout(0, 0));

        // шапка
        JPanel head = new JPanel(new BorderLayout());
        head.setBackground(BG);
        head.setBorder(new EmptyBorder(18, 22, 6, 22));
        JLabel title = new JLabel("Прогноз потребления на сутки вперёд");
        title.setFont(title.getFont().deriveFont(Font.BOLD, 24f));
        title.setForeground(INK);
        JLabel sub = new JLabel("ОЭС Северо-Запада · нейросеть Chronos-2 · прогноз выпускается накануне в 09:00 по данным СО ЕЭС и прогнозу погоды");
        sub.setForeground(INK2);
        head.add(title, BorderLayout.NORTH);
        head.add(sub, BorderLayout.SOUTH);
        add(head, BorderLayout.NORTH);

        // левая панель управления
        JPanel side = card(new JPanel());
        side.setLayout(new BoxLayout(side, BoxLayout.Y_AXIS));
        side.setPreferredSize(new Dimension(290, 0));
        dateSpin.setEditor(new JSpinner.DateEditor(dateSpin, "dd.MM.yyyy"));
        setDate(LocalDate.now().plusDays(1));
        side.add(caption("Сутки прогноза"));
        side.add(full(dateSpin));
        side.add(Box.createVerticalStrut(14));
        side.add(caption("Модель"));
        side.add(full(modelBox));
        side.add(Box.createVerticalStrut(10));
        update.setOpaque(false);
        update.setForeground(INK2);
        side.add(full(update));
        side.add(Box.createVerticalStrut(16));
        runBtn.setFont(runBtn.getFont().deriveFont(Font.BOLD));
        for (JButton b : List.of(runBtn, tomorrowBtn, saveBtn)) { side.add(full(b)); side.add(Box.createVerticalStrut(8)); }
        saveBtn.setEnabled(false);
        progress.setIndeterminate(true);
        progress.setVisible(false);
        side.add(full(progress));
        side.add(Box.createVerticalStrut(18));
        side.add(caption("Сводка"));
        for (String k : List.of("Сутки", "Тип дня", "Пик", "Энергия за сутки", "Средняя температура", "Ошибка по факту", "Время расчёта")) {
            JPanel line = new JPanel(new BorderLayout());
            line.setOpaque(false);
            JLabel kl = new JLabel(k), vl = new JLabel("—");
            kl.setForeground(INK2);
            vl.setForeground(INK);
            vl.setFont(vl.getFont().deriveFont(Font.BOLD));
            line.add(kl, BorderLayout.WEST);
            line.add(vl, BorderLayout.EAST);
            line.setMaximumSize(new Dimension(Integer.MAX_VALUE, 26));
            line.setAlignmentX(LEFT_ALIGNMENT);
            stats.put(k, vl);
            side.add(line);
        }
        side.add(Box.createVerticalGlue());
        JPanel west = new JPanel(new BorderLayout());
        west.setBackground(BG);
        west.setBorder(new EmptyBorder(10, 22, 18, 10));
        west.add(side);
        add(west, BorderLayout.WEST);

        // вкладки: график, таблица, журнал
        JTable table = new JTable(tableModel);
        table.setRowHeight(24);
        table.setShowVerticalLines(false);
        table.setGridColor(GRID);
        DefaultTableCellRenderer right = new DefaultTableCellRenderer();
        right.setHorizontalAlignment(SwingConstants.RIGHT);
        for (int i = 0; i < tableModel.getColumnCount(); i++) table.getColumnModel().getColumn(i).setCellRenderer(right);
        logArea.setEditable(false);
        logArea.setFont(new Font(Font.MONOSPACED, Font.PLAIN, 12));
        JTabbedPane tabs = new JTabbedPane();
        tabs.addTab("График", chart);
        tabs.addTab("Таблица", new JScrollPane(table));
        tabs.addTab("Журнал", new JScrollPane(logArea));
        JPanel center = card(new JPanel(new BorderLayout()));
        center.add(tabs);
        JPanel centerWrap = new JPanel(new BorderLayout());
        centerWrap.setBackground(BG);
        centerWrap.setBorder(new EmptyBorder(10, 10, 18, 22));
        centerWrap.add(center);
        add(centerWrap, BorderLayout.CENTER);

        status.setForeground(INK2);
        status.setBorder(new EmptyBorder(0, 22, 12, 22));
        add(status, BorderLayout.SOUTH);

        runBtn.addActionListener(e -> runForecast());
        tomorrowBtn.addActionListener(e -> { setDate(LocalDate.now().plusDays(1)); update.setSelected(true); runForecast(); });
        saveBtn.addActionListener(e -> saveCsv());
        pack();
        setSize(1180, 760);
        setLocationRelativeTo(null);
    }

    static JPanel card(JPanel p) {
        p.setBackground(CARD);
        p.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(GRID, 1, true), new EmptyBorder(16, 16, 16, 16)));
        return p;
    }

    static JLabel caption(String t) {
        JLabel l = new JLabel(t);
        l.setForeground(INK2);
        l.setFont(l.getFont().deriveFont(Font.PLAIN, 12f));
        l.setBorder(new EmptyBorder(0, 0, 4, 0));
        l.setAlignmentX(LEFT_ALIGNMENT);
        return l;
    }

    static <T extends JComponent> T full(T c) {
        c.setAlignmentX(LEFT_ALIGNMENT);
        c.setMaximumSize(new Dimension(Integer.MAX_VALUE, c.getPreferredSize().height + 4));
        return c;
    }

    void setDate(LocalDate d) {
        dateSpin.setValue(Date.from(d.atStartOfDay(ZoneId.systemDefault()).toInstant()));
    }

    LocalDate getDate() {
        return ((Date) dateSpin.getValue()).toInstant().atZone(ZoneId.systemDefault()).toLocalDate();
    }

    void runForecast() {
        String model = MODELS[modelBox.getSelectedIndex()][0];
        LocalDate d = getDate();
        File python = new File(root, ".venv/bin/python");
        if (!python.exists()) {
            JOptionPane.showMessageDialog(this, "Не найдено окружение Python: " + python, "Ошибка", JOptionPane.ERROR_MESSAGE);
            return;
        }
        List<String> cmd = new ArrayList<>(List.of(python.getPath(), "model/predict.py", "--date", d.toString(), "--model", model));
        if (update.isSelected()) cmd.add("--update");
        setBusy(true, "Считаю прогноз на " + d.format(java.time.format.DateTimeFormatter.ofPattern("dd.MM.yyyy")) + "… (обычно около минуты)");
        logArea.append("\n$ " + String.join(" ", cmd) + "\n");

        new SwingWorker<Boolean, String>() {
            final List<Row> newRows = new ArrayList<>();
            final Map<String, String> newMeta = new HashMap<>();
            String lastError = "";

            @Override protected Boolean doInBackground() throws Exception {
                ProcessBuilder pb = new ProcessBuilder(cmd).directory(root).redirectErrorStream(true);
                pb.environment().put("PYTHONUNBUFFERED", "1");
                Process p = pb.start();
                boolean inResult = false;
                try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = r.readLine()) != null) {
                        if (line.equals("RESULT_BEGIN")) { inResult = true; continue; }
                        if (line.equals("RESULT_END")) { inResult = false; continue; }
                        if (inResult && line.startsWith("meta ")) {
                            String[] kv = line.substring(5).split(" ", 2);
                            newMeta.put(kv[0], kv.length > 1 ? kv[1] : "");
                        } else if (inResult && line.startsWith("row ")) {
                            String[] f = line.split(" ");
                            newRows.add(new Row(Integer.parseInt(f[1]), Double.parseDouble(f[2]), Double.parseDouble(f[3]),
                                    Double.parseDouble(f[4]), f[5].equals("-") ? null : Double.parseDouble(f[5]),
                                    f[6].equals("-") ? null : Double.parseDouble(f[6])));
                        } else if (!line.contains("Warning") && !line.contains("warnings.warn") && !line.contains("MallocStackLogging")) {
                            publish(line);
                            if (!line.isBlank()) lastError = line;
                        }
                    }
                }
                return p.waitFor() == 0 && newRows.size() == 24;
            }

            @Override protected void process(List<String> lines) {
                for (String l : lines) logArea.append(l + "\n");
                logArea.setCaretPosition(logArea.getDocument().getLength());
                String last = lines.get(lines.size() - 1).trim();
                if (!last.isEmpty()) status.setText(last);
            }

            @Override protected void done() {
                boolean ok;
                try { ok = get(); } catch (Exception ex) { ok = false; lastError = ex.getMessage(); }
                setBusy(false, ok ? "Готово" : "Ошибка: " + lastError);
                if (!ok) {
                    JOptionPane.showMessageDialog(ForecastApp.this, lastError, "Прогноз не получен", JOptionPane.WARNING_MESSAGE);
                    return;
                }
                rows = newRows;
                meta = newMeta;
                showResult();
            }
        }.execute();
    }

    void setBusy(boolean busy, String msg) {
        progress.setVisible(busy);
        for (JComponent c : List.of(runBtn, tomorrowBtn, dateSpin, modelBox, update)) c.setEnabled(!busy);
        saveBtn.setEnabled(!busy && !rows.isEmpty());
        status.setText(msg);
    }

    static String mw(double v) { return String.format(Locale.forLanguageTag("ru"), "%,.0f", v); }

    void showResult() {
        tableModel.setRowCount(0);
        for (Row r : rows) {
            String err = r.actual() == null ? "" : String.format(Locale.forLanguageTag("ru"), "%+.1f", (r.fc() - r.actual()) / r.actual() * 100);
            tableModel.addRow(new Object[]{String.format("%02d:00", r.hour()), mw(r.fc()), mw(r.p10()), mw(r.p90()),
                    r.actual() == null ? "—" : mw(r.actual()), err, r.temp() == null ? "—" : String.format(Locale.forLanguageTag("ru"), "%.1f", r.temp())});
        }
        stats.get("Сутки").setText(meta.getOrDefault("date", "—"));
        stats.get("Тип дня").setText(meta.getOrDefault("day_type", "—"));
        stats.get("Пик").setText(mw(Double.parseDouble(meta.get("peak"))) + " МВт в " + meta.get("peak_hour") + ":00");
        stats.get("Энергия за сутки").setText(meta.get("energy").replace('.', ',') + " ГВт·ч");
        String t = meta.getOrDefault("temp_mean", "-");
        stats.get("Средняя температура").setText(t.equals("-") ? "—" : t.replace('.', ',') + " °C");
        String m = meta.getOrDefault("mape", "-");
        JLabel ml = stats.get("Ошибка по факту");
        ml.setText(m.equals("-") ? "факта ещё нет" : m.replace('.', ',') + " %");
        ml.setForeground(m.equals("-") ? INK2 : GOOD);
        stats.get("Время расчёта").setText(meta.getOrDefault("seconds", "—") + " с (" + meta.getOrDefault("device", "") + ")");
        status.setText("Прогноз на " + meta.get("date") + " выпущен как на " + meta.get("issued") + " · " + meta.get("model"));
        chart.repaint();
        saveBtn.setEnabled(true);
    }

    void saveCsv() {
        JFileChooser fc = new JFileChooser();
        fc.setSelectedFile(new File("прогноз_" + meta.getOrDefault("date", "").replace('.', '-') + ".csv"));
        if (fc.showSaveDialog(this) != JFileChooser.APPROVE_OPTION) return;
        try (PrintWriter w = new PrintWriter(fc.getSelectedFile(), StandardCharsets.UTF_8)) {
            w.print('﻿');
            w.println("hour;forecast_mw;p10_mw;p90_mw;actual_mw;temp_c");
            for (Row r : rows)
                w.printf(Locale.ROOT, "%d;%.0f;%.0f;%.0f;%s;%s%n", r.hour(), r.fc(), r.p10(), r.p90(),
                        r.actual() == null ? "" : String.format(Locale.ROOT, "%.0f", r.actual()),
                        r.temp() == null ? "" : String.format(Locale.ROOT, "%.1f", r.temp()));
            status.setText("Сохранено: " + fc.getSelectedFile().getName());
        } catch (Exception ex) {
            JOptionPane.showMessageDialog(this, ex.getMessage(), "Не удалось сохранить", JOptionPane.ERROR_MESSAGE);
        }
    }

    /** График: коридор 10–90 %, прогноз (синий), факт (чёрный) и подсказка при наведении. */
    class ChartPanel extends JPanel {
        int hover = -1;

        ChartPanel() {
            setBackground(CARD);
            MouseAdapter ma = new MouseAdapter() {
                @Override public void mouseMoved(MouseEvent e) {
                    if (rows.isEmpty()) return;
                    int l = 70, r = getWidth() - 24;
                    int h = (int) Math.round((e.getX() - l) / (double) (r - l) * 23);
                    hover = (h < 0 || h > 23) ? -1 : h;
                    repaint();
                }
                @Override public void mouseExited(MouseEvent e) { hover = -1; repaint(); }
            };
            addMouseMotionListener(ma);
            addMouseListener(ma);
        }

        @Override protected void paintComponent(Graphics g0) {
            super.paintComponent(g0);
            Graphics2D g = (Graphics2D) g0;
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
            int W = getWidth(), H = getHeight(), l = 70, r = W - 24, t = 40, b = H - 46;
            if (rows.isEmpty()) {
                g.setColor(INK2);
                g.setFont(getFont().deriveFont(15f));
                String s = "Здесь появится почасовой прогноз";
                g.drawString(s, (W - g.getFontMetrics().stringWidth(s)) / 2, H / 2);
                return;
            }
            double lo = Double.MAX_VALUE, hi = -Double.MAX_VALUE;
            for (Row row : rows) {
                lo = Math.min(lo, Math.min(row.p10(), row.actual() == null ? row.p10() : row.actual()));
                hi = Math.max(hi, Math.max(row.p90(), row.actual() == null ? row.p90() : row.actual()));
            }
            double step = (hi - lo) > 2500 ? 1000 : 500;
            double ylo = Math.floor(lo / step) * step, yhi = Math.ceil(hi / step) * step;
            java.util.function.DoubleUnaryOperator Y = v -> b - (v - ylo) / (yhi - ylo) * (b - t);
            java.util.function.IntToDoubleFunction X = h -> l + h / 23.0 * (r - l);

            g.setFont(getFont().deriveFont(12f));
            FontMetrics fm = g.getFontMetrics();
            for (double v = ylo; v <= yhi + 1e-6; v += step) {
                int y = (int) Y.applyAsDouble(v);
                g.setColor(GRID);
                g.drawLine(l, y, r, y);
                g.setColor(INK2);
                String s = mw(v);
                g.drawString(s, l - 8 - fm.stringWidth(s), y + 4);
            }
            for (int h = 0; h < 24; h += 3) {
                String s = String.format("%02d:00", h);
                g.drawString(s, (int) X.applyAsDouble(h) - fm.stringWidth(s) / 2, b + 20);
            }
            g.drawString("МВт", 10, t - 14);

            Path2D band = new Path2D.Double();
            for (Row row : rows) { double x = X.applyAsDouble(row.hour()), y = Y.applyAsDouble(row.p90()); if (row.hour() == 0) band.moveTo(x, y); else band.lineTo(x, y); }
            for (int i = rows.size() - 1; i >= 0; i--) band.lineTo(X.applyAsDouble(rows.get(i).hour()), Y.applyAsDouble(rows.get(i).p10()));
            band.closePath();
            g.setColor(new Color(0, 113, 227, 40));
            g.fill(band);

            Path2D fc = new Path2D.Double(), act = new Path2D.Double();
            boolean penA = false;
            for (Row row : rows) {
                double x = X.applyAsDouble(row.hour());
                if (row.hour() == 0) fc.moveTo(x, Y.applyAsDouble(row.fc())); else fc.lineTo(x, Y.applyAsDouble(row.fc()));
                if (row.actual() != null) {
                    if (penA) act.lineTo(x, Y.applyAsDouble(row.actual())); else act.moveTo(x, Y.applyAsDouble(row.actual()));
                    penA = true;
                } else penA = false;
            }
            g.setStroke(new BasicStroke(2.6f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
            g.setColor(INK);
            g.draw(act);
            g.setStroke(new BasicStroke(2.4f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND, 10f, new float[]{8f, 5f}, 0f));
            g.setColor(ACCENT);
            g.draw(fc);

            // легенда
            g.setStroke(new BasicStroke(1f));
            int lx = l, ly = 16;
            g.setColor(ACCENT); g.fillRect(lx, ly - 5, 22, 3); g.setColor(INK2); g.drawString("прогноз", lx + 28, ly);
            lx += 100;
            g.setColor(new Color(0, 113, 227, 60)); g.fillRect(lx, ly - 9, 22, 10); g.setColor(INK2); g.drawString("коридор 10–90 %", lx + 28, ly);
            lx += 150;
            if (rows.stream().anyMatch(rr -> rr.actual() != null)) { g.setColor(INK); g.fillRect(lx, ly - 5, 22, 3); g.setColor(INK2); g.drawString("факт", lx + 28, ly); }

            if (hover >= 0) {
                Row row = rows.get(hover);
                int x = (int) X.applyAsDouble(hover);
                g.setColor(INK2);
                g.drawLine(x, t, x, b);
                g.setColor(ACCENT);
                int fy = (int) Y.applyAsDouble(row.fc());
                g.fillOval(x - 5, fy - 5, 10, 10);
                if (row.actual() != null) { g.setColor(INK); int ay = (int) Y.applyAsDouble(row.actual()); g.fillOval(x - 5, ay - 5, 10, 10); }
                List<String> lines = new ArrayList<>(List.of(String.format("%02d:00", hour(row)), "Прогноз: " + mw(row.fc()) + " МВт",
                        "Коридор: " + mw(row.p10()) + "–" + mw(row.p90())));
                if (row.actual() != null) lines.add("Факт: " + mw(row.actual()) + " МВт");
                if (row.temp() != null) lines.add(String.format(Locale.forLanguageTag("ru"), "Температура: %.1f °C", row.temp()));
                int bw = lines.stream().mapToInt(fm::stringWidth).max().orElse(80) + 20, bh = lines.size() * 18 + 12;
                int bx = x + 14 + bw > r ? x - 14 - bw : x + 14, by = t + 8;
                g.setColor(new Color(255, 255, 255, 240));
                g.fillRoundRect(bx, by, bw, bh, 12, 12);
                g.setColor(GRID);
                g.drawRoundRect(bx, by, bw, bh, 12, 12);
                g.setColor(INK);
                for (int i = 0; i < lines.size(); i++) g.drawString(lines.get(i), bx + 10, by + 20 + i * 18);
            }
        }

        int hour(Row r) { return r.hour(); }
    }

    public static void main(String[] args) {
        System.setProperty("apple.awt.application.name", "Прогноз потребления");
        File root = new File(args.length > 0 ? args[0] : System.getProperty("user.dir")).getAbsoluteFile();
        SwingUtilities.invokeLater(() -> {
            try { UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName()); } catch (Exception ignored) {}
            new ForecastApp(root).setVisible(true);
        });
    }
}
