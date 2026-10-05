import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableCellRenderer;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.awt.event.MouseAdapter;
import java.awt.event.MouseEvent;
import java.awt.geom.Path2D;
import java.awt.geom.RoundRectangle2D;
import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.List;
import java.util.function.Consumer;

/**
 * Прогноз потребления ОЭС Северо-Запада моделью Chronos-2 — интерфейс в стиле сайта проекта
 * (светлый фон, белые карточки, кнопки-таблетки, сегментные переключатели).
 * Считает model/predict.py из виртуального окружения проекта.
 */
public class ForecastApp extends JFrame {
    static final Color BG = new Color(0xF5F5F7), CARD = Color.WHITE, INK = new Color(0x1D1D1F), INK2 = new Color(0x6E6E73),
            INK3 = new Color(0x86868B), ACCENT = new Color(0x0071E3), FILL = new Color(0xF0F0F3), LINE = new Color(0xE8E8ED),
            GOOD = new Color(0x1E9E5A);
    static final String FONT = pickFont();
    static final Locale RU = Locale.forLanguageTag("ru");
    static final DateTimeFormatter DMY = DateTimeFormatter.ofPattern("dd.MM.yyyy");
    static final String[][] MODELS = {{"chronos-lora", "Chronos-2 LoRA"}, {"chronos-zs", "Без дообучения"}};

    record Row(int hour, double fc, double p10, double p90, Double actual, Double temp) {}

    final File root;
    LocalDate date = LocalDate.now().plusDays(1);
    int model = 0;
    boolean update = true, busy = false;
    List<Row> rows = new ArrayList<>();
    Map<String, String> meta = new HashMap<>();

    final JLabel dateLabel = label("", 15, Font.BOLD, INK);
    final JLabel status = label("Выберите сутки и нажмите «Сделать прогноз»", 13, Font.PLAIN, INK3);
    final Map<String, JLabel[]> kpi = new LinkedHashMap<>();
    final Pill runBtn = new Pill("Сделать прогноз", true), tomorrowBtn = new Pill("Завтра", false), csvBtn = new Pill("Сохранить CSV", false);
    final Pill prevBtn = new Pill("‹", false), nextBtn = new Pill("›", false);
    final Segmented modelSeg = new Segmented(Arrays.stream(MODELS).map(m -> m[1]).toArray(String[]::new), i -> model = i);
    final Toggle updToggle = new Toggle(true, v -> update = v);
    final ChartPanel chart = new ChartPanel();
    final DefaultTableModel tableModel = new DefaultTableModel(new String[]{"Час", "Прогноз", "10 %", "90 %", "Факт", "Ошибка", "Темп."}, 0) {
        @Override public boolean isCellEditable(int r, int c) { return false; }
    };
    final JTextArea logArea = new JTextArea();
    final CardLayout views = new CardLayout();
    final JPanel viewHost = new JPanel(views);

    static String pickFont() {
        Set<String> have = new HashSet<>(Arrays.asList(GraphicsEnvironment.getLocalGraphicsEnvironment().getAvailableFontFamilyNames()));
        for (String f : List.of("SF Pro Text", "SF Pro Display", "Helvetica Neue", "Segoe UI", "Arial")) if (have.contains(f)) return f;
        return Font.SANS_SERIF;
    }

    static JLabel label(String t, float size, int style, Color c) {
        JLabel l = new JLabel(t);
        l.setFont(new Font(FONT, style, Math.round(size)).deriveFont(size));
        l.setForeground(c);
        return l;
    }

    static String mw(double v) { return String.format(RU, "%,.0f", v).replace(' ', ' '); }

    public ForecastApp(File root) {
        super("Прогноз потребления — ОЭС Северо-Запада");
        this.root = root;
        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setMinimumSize(new Dimension(1000, 720));
        JPanel page = new JPanel(new BorderLayout(0, 18));
        page.setBackground(BG);
        page.setBorder(new EmptyBorder(26, 30, 18, 30));
        setContentPane(page);

        // шапка
        JPanel head = transparent(new GridLayout(0, 1, 0, 2));
        head.add(label("ОЭС Северо-Запада · прогноз на сутки вперёд", 13, Font.BOLD, ACCENT));
        head.add(label("Прогноз потребления", 34, Font.BOLD, INK));
        head.add(label("Нейросеть Chronos-2 · прогноз выпускается накануне в 09:00 по данным СО ЕЭС и прогнозу погоды", 14, Font.PLAIN, INK2));

        // панель управления
        Card controls = new Card(new FlowLayout(FlowLayout.LEFT, 12, 8));
        controls.setBorder(new EmptyBorder(10, 14, 10, 14));
        controls.add(caption("Сутки"));
        controls.add(prevBtn);
        dateLabel.setPreferredSize(new Dimension(104, 30));
        dateLabel.setHorizontalAlignment(SwingConstants.CENTER);
        controls.add(dateLabel);
        controls.add(nextBtn);
        controls.add(gap(10));
        controls.add(caption("Модель"));
        controls.add(modelSeg);
        controls.add(gap(10));
        controls.add(updToggle);
        controls.add(caption("Докачивать свежие данные с сайтов СО ЕЭС и Open-Meteo"));
        csvBtn.setEnabled(false);
        JPanel actions = transparent(new FlowLayout(FlowLayout.RIGHT, 10, 0));
        actions.add(csvBtn);
        actions.add(tomorrowBtn);
        actions.add(runBtn);
        JPanel headRow = transparent(new BorderLayout());
        headRow.add(head, BorderLayout.WEST);
        JPanel actWrap = transparent(new BorderLayout());
        actWrap.add(actions, BorderLayout.SOUTH);
        headRow.add(actWrap, BorderLayout.EAST);

        // карточки с цифрами
        JPanel kpis = transparent(new GridLayout(1, 4, 16, 0));
        for (String[] k : new String[][]{{"Пик нагрузки", ""}, {"Энергия за сутки", ""}, {"Средняя температура", ""}, {"Ошибка по факту", ""}}) {
            Card c = new Card(new GridLayout(0, 1, 0, 2));
            c.setBorder(new EmptyBorder(14, 18, 14, 18));
            JLabel kl = label(k[0], 13, Font.PLAIN, INK3), vl = label("—", 28, Font.BOLD, kpi.isEmpty() ? ACCENT : INK), sl = label(" ", 12.5f, Font.PLAIN, INK2);
            c.add(kl); c.add(vl); c.add(sl);
            kpi.put(k[0], new JLabel[]{vl, sl});
            kpis.add(c);
        }

        JPanel north = transparent(new BorderLayout(0, 16));
        north.add(headRow, BorderLayout.NORTH);
        north.add(controls, BorderLayout.CENTER);
        north.add(kpis, BorderLayout.SOUTH);
        page.add(north, BorderLayout.NORTH);

        // основная карточка: график / таблица / журнал
        Card main = new Card(new BorderLayout(0, 10));
        main.setBorder(new EmptyBorder(16, 20, 16, 20));
        JPanel mainHead = transparent(new BorderLayout());
        mainHead.add(label("Почасовой прогноз", 20, Font.BOLD, INK), BorderLayout.WEST);
        Segmented tabs = new Segmented(new String[]{"График", "Таблица", "Журнал"}, i -> views.show(viewHost, String.valueOf(i)));
        mainHead.add(tabs, BorderLayout.EAST);
        main.add(mainHead, BorderLayout.NORTH);

        JTable table = new JTable(tableModel);
        table.setRowHeight(30);
        table.setShowGrid(false);
        table.setIntercellSpacing(new Dimension(0, 0));
        table.setFont(new Font(FONT, Font.PLAIN, 13));
        table.setSelectionBackground(FILL);
        table.setSelectionForeground(INK);
        table.getTableHeader().setDefaultRenderer((t, v, s, f, r, c) -> {
            JLabel l = label(String.valueOf(v), 12, Font.PLAIN, INK3);
            l.setHorizontalAlignment(c == 0 ? SwingConstants.LEFT : SwingConstants.RIGHT);
            l.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createMatteBorder(0, 0, 1, 0, LINE), new EmptyBorder(6, 10, 6, 10)));
            return l;
        });
        DefaultTableCellRenderer cell = new DefaultTableCellRenderer() {
            @Override public Component getTableCellRendererComponent(JTable t, Object v, boolean s, boolean f, int r, int c) {
                JLabel l = (JLabel) super.getTableCellRendererComponent(t, v, s, f, r, c);
                l.setHorizontalAlignment(c == 0 ? SwingConstants.LEFT : SwingConstants.RIGHT);
                l.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createMatteBorder(0, 0, 1, 0, LINE), new EmptyBorder(0, 10, 0, 10)));
                l.setForeground(c == 1 ? ACCENT : INK);
                l.setFont(new Font(FONT, c == 1 ? Font.BOLD : Font.PLAIN, 13));
                l.setBackground(s ? FILL : CARD);
                return l;
            }
        };
        for (int i = 0; i < tableModel.getColumnCount(); i++) table.getColumnModel().getColumn(i).setCellRenderer(cell);
        JScrollPane tableScroll = new JScrollPane(table);
        tableScroll.setBorder(null);
        tableScroll.getViewport().setBackground(CARD);
        logArea.setEditable(false);
        logArea.setFont(new Font(Font.MONOSPACED, Font.PLAIN, 12));
        logArea.setForeground(INK2);
        logArea.setBorder(new EmptyBorder(8, 8, 8, 8));
        JScrollPane logScroll = new JScrollPane(logArea);
        logScroll.setBorder(null);
        viewHost.setOpaque(false);
        viewHost.add(chart, "0");
        viewHost.add(tableScroll, "1");
        viewHost.add(logScroll, "2");
        main.add(viewHost, BorderLayout.CENTER);
        page.add(main, BorderLayout.CENTER);
        page.add(status, BorderLayout.SOUTH);

        prevBtn.addActionListener(e -> { date = date.minusDays(1); refreshDate(); });
        nextBtn.addActionListener(e -> { date = date.plusDays(1); refreshDate(); });
        runBtn.addActionListener(e -> runForecast());
        tomorrowBtn.addActionListener(e -> { date = LocalDate.now().plusDays(1); refreshDate(); updToggle.set(true); runForecast(); });
        csvBtn.addActionListener(e -> saveCsv());
        refreshDate();
        setSize(1240, 820);
        setLocationRelativeTo(null);
    }

    static JPanel transparent(LayoutManager lm) { JPanel p = new JPanel(lm); p.setOpaque(false); return p; }
    static JLabel caption(String t) { return label(t, 13, Font.PLAIN, INK2); }
    static Component gap(int w) { return Box.createHorizontalStrut(w); }
    void refreshDate() { dateLabel.setText(date.format(DMY)); }

    // ---------- расчёт ----------
    void runForecast() {
        if (busy) return;
        File python = new File(root, ".venv/bin/python");
        if (!python.exists()) { JOptionPane.showMessageDialog(this, "Не найдено окружение Python: " + python); return; }
        List<String> cmd = new ArrayList<>(List.of(python.getPath(), "model/predict.py", "--date", date.toString(), "--model", MODELS[model][0]));
        if (update) cmd.add("--update");
        setBusy(true, "Считаю прогноз на " + date.format(DMY) + "… обычно 30–60 секунд");
        logArea.append("\n$ " + String.join(" ", cmd) + "\n");
        new SwingWorker<Boolean, String>() {
            final List<Row> nr = new ArrayList<>();
            final Map<String, String> nm = new HashMap<>();
            String lastLine = "";

            @Override protected Boolean doInBackground() throws Exception {
                ProcessBuilder pb = new ProcessBuilder(cmd).directory(root).redirectErrorStream(true);
                pb.environment().put("PYTHONUNBUFFERED", "1");
                Process p = pb.start();
                boolean in = false;
                try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
                    for (String line; (line = r.readLine()) != null; ) {
                        if (line.equals("RESULT_BEGIN")) { in = true; continue; }
                        if (line.equals("RESULT_END")) { in = false; continue; }
                        if (in && line.startsWith("meta ")) { String[] kv = line.substring(5).split(" ", 2); nm.put(kv[0], kv.length > 1 ? kv[1] : ""); }
                        else if (in && line.startsWith("row ")) {
                            String[] f = line.split(" ");
                            nr.add(new Row(Integer.parseInt(f[1]), Double.parseDouble(f[2]), Double.parseDouble(f[3]), Double.parseDouble(f[4]),
                                    f[5].equals("-") ? null : Double.valueOf(f[5]), f[6].equals("-") ? null : Double.valueOf(f[6])));
                        } else if (!line.contains("Warning") && !line.contains("warnings.warn") && !line.contains("MallocStackLogging") && !line.contains("Loading weights")) {
                            publish(line);
                            if (!line.isBlank()) lastLine = line.trim();
                        }
                    }
                }
                return p.waitFor() == 0 && nr.size() == 24;
            }

            @Override protected void process(List<String> lines) {
                for (String l : lines) logArea.append(l + "\n");
                logArea.setCaretPosition(logArea.getDocument().getLength());
                String l = lines.get(lines.size() - 1).trim();
                if (!l.isEmpty()) status.setText(l);
            }

            @Override protected void done() {
                boolean ok;
                try { ok = get(); } catch (Exception ex) { ok = false; lastLine = ex.getMessage(); }
                setBusy(false, ok ? "Готово" : "Не удалось: " + lastLine);
                if (!ok) { JOptionPane.showMessageDialog(ForecastApp.this, lastLine, "Прогноз не получен", JOptionPane.WARNING_MESSAGE); return; }
                rows = nr; meta = nm;
                showResult();
            }
        }.execute();
    }

    void setBusy(boolean b, String msg) {
        busy = b;
        for (JComponent c : List.of(runBtn, tomorrowBtn, prevBtn, nextBtn, modelSeg, updToggle)) c.setEnabled(!b);
        csvBtn.setEnabled(!b && !rows.isEmpty());
        runBtn.setText(b ? "Считаю…" : "Сделать прогноз");
        status.setText(msg);
        chart.busy = b;
        chart.repaint();
    }

    void showResult() {
        tableModel.setRowCount(0);
        for (Row r : rows) {
            String err = r.actual() == null ? "" : String.format(RU, "%+.1f %%", (r.fc() - r.actual()) / r.actual() * 100);
            tableModel.addRow(new Object[]{String.format("%02d:00", r.hour()), mw(r.fc()) + " МВт", mw(r.p10()), mw(r.p90()),
                    r.actual() == null ? "—" : mw(r.actual()), err, r.temp() == null ? "—" : String.format(RU, "%.1f °C", r.temp())});
        }
        set("Пик нагрузки", mw(Double.parseDouble(meta.get("peak"))) + " МВт", "в " + meta.get("peak_hour") + ":00 · " + meta.getOrDefault("day_type", "") + " день");
        set("Энергия за сутки", meta.get("energy").replace('.', ',') + " ГВт·ч", "сумма 24 часов");
        String t = meta.getOrDefault("temp_mean", "-");
        set("Средняя температура", t.equals("-") ? "—" : t.replace('.', ',') + " °C", "прогноз погоды на сутки");
        String m = meta.getOrDefault("mape", "-");
        set("Ошибка по факту", m.equals("-") ? "—" : m.replace('.', ',') + " %", m.equals("-") ? "факта ещё нет" : "по " + meta.get("actual_hours") + " часам");
        kpi.get("Ошибка по факту")[0].setForeground(m.equals("-") ? INK3 : GOOD);
        status.setText("Прогноз на " + meta.get("date") + " выпущен как на " + meta.get("issued") + " · " + meta.get("model") + " · " + meta.get("seconds") + " с");
        chart.repaint();
        csvBtn.setEnabled(true);
    }

    void set(String k, String v, String sub) { kpi.get(k)[0].setText(v); kpi.get(k)[1].setText(sub); }

    void saveCsv() {
        JFileChooser fc = new JFileChooser();
        fc.setSelectedFile(new File("прогноз_" + meta.getOrDefault("date", "").replace('.', '-') + ".csv"));
        if (fc.showSaveDialog(this) != JFileChooser.APPROVE_OPTION) return;
        try (PrintWriter w = new PrintWriter(fc.getSelectedFile(), StandardCharsets.UTF_8)) {
            w.print('﻿');
            w.println("hour;forecast_mw;p10_mw;p90_mw;actual_mw;temp_c");
            for (Row r : rows) w.printf(Locale.ROOT, "%d;%.0f;%.0f;%.0f;%s;%s%n", r.hour(), r.fc(), r.p10(), r.p90(),
                    r.actual() == null ? "" : String.format(Locale.ROOT, "%.0f", r.actual()), r.temp() == null ? "" : String.format(Locale.ROOT, "%.1f", r.temp()));
            status.setText("Сохранено: " + fc.getSelectedFile().getName());
        } catch (Exception ex) { JOptionPane.showMessageDialog(this, ex.getMessage()); }
    }

    // ---------- компоненты в стиле сайта ----------
    static Graphics2D smooth(Graphics g0) {
        Graphics2D g = (Graphics2D) g0.create();
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_STROKE_CONTROL, RenderingHints.VALUE_STROKE_PURE);
        return g;
    }

    /** Белая карточка со скруглением 20 px и мягкой тенью. */
    static class Card extends JPanel {
        Card(LayoutManager lm) { super(lm); setOpaque(false); }
        @Override protected void paintComponent(Graphics g0) {
            Graphics2D g = smooth(g0);
            for (int i = 6; i >= 1; i--) {
                g.setColor(new Color(0, 0, 0, 3));
                g.fill(new RoundRectangle2D.Double(-i * 0.3, i * 0.6, getWidth() + i * 0.6, getHeight(), 22 + i, 22 + i));
            }
            g.setColor(CARD);
            g.fill(new RoundRectangle2D.Double(0, 0, getWidth(), getHeight() - 2, 20, 20));
            g.dispose();
        }
    }

    /** Кнопка-таблетка: основная — синяя, обычная — серая. */
    static class Pill extends JButton {
        final boolean primary;
        boolean hover;
        Pill(String t, boolean primary) {
            super(t);
            this.primary = primary;
            setFont(new Font(FONT, primary ? Font.BOLD : Font.PLAIN, 14));
            setContentAreaFilled(false); setBorderPainted(false); setFocusPainted(false); setOpaque(false);
            setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
            setBorder(new EmptyBorder(7, 16, 7, 16));
            addMouseListener(new MouseAdapter() {
                @Override public void mouseEntered(MouseEvent e) { hover = true; repaint(); }
                @Override public void mouseExited(MouseEvent e) { hover = false; repaint(); }
            });
        }
        @Override protected void paintComponent(Graphics g0) {
            Graphics2D g = smooth(g0);
            Color bg = primary ? (hover ? new Color(0x0077ED) : ACCENT) : (hover ? LINE : FILL);
            if (!isEnabled()) bg = primary ? new Color(0x8FBDF2) : FILL;
            g.setColor(bg);
            g.fill(new RoundRectangle2D.Double(0, 0, getWidth(), getHeight(), getHeight(), getHeight()));
            g.setFont(getFont());
            FontMetrics fm = g.getFontMetrics();
            g.setColor(primary ? Color.WHITE : (isEnabled() ? INK : INK3));
            g.drawString(getText(), (getWidth() - fm.stringWidth(getText())) / 2, (getHeight() + fm.getAscent() - fm.getDescent()) / 2);
            g.dispose();
        }
    }

    /** Сегментный переключатель как в macOS/iOS. */
    static class Segmented extends JComponent {
        final String[] items;
        final Consumer<Integer> onChange;
        int sel = 0;
        Segmented(String[] items, Consumer<Integer> onChange) {
            this.items = items; this.onChange = onChange;
            setFont(new Font(FONT, Font.PLAIN, 13));
            setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
            addMouseListener(new MouseAdapter() {
                @Override public void mouseClicked(MouseEvent e) {
                    if (!isEnabled()) return;
                    int i = Math.min(items.length - 1, e.getX() * items.length / Math.max(1, getWidth()));
                    if (i != sel) { sel = i; repaint(); onChange.accept(i); }
                }
            });
        }
        @Override public Dimension getPreferredSize() {
            FontMetrics fm = getFontMetrics(getFont());
            int w = Arrays.stream(items).mapToInt(fm::stringWidth).max().orElse(60) + 30;
            return new Dimension(w * items.length + 6, 32);
        }
        @Override protected void paintComponent(Graphics g0) {
            Graphics2D g = smooth(g0);
            int w = getWidth(), h = getHeight(), sw = (w - 6) / items.length;
            g.setColor(FILL);
            g.fill(new RoundRectangle2D.Double(0, 0, w, h, h, h));
            g.setColor(new Color(0, 0, 0, 18));
            g.fill(new RoundRectangle2D.Double(3 + sel * sw, 4, sw, h - 6, h - 6, h - 6));
            g.setColor(CARD);
            g.fill(new RoundRectangle2D.Double(3 + sel * sw, 3, sw, h - 6, h - 6, h - 6));
            FontMetrics fm = g.getFontMetrics(getFont());
            for (int i = 0; i < items.length; i++) {
                g.setFont(getFont().deriveFont(i == sel ? Font.BOLD : Font.PLAIN));
                fm = g.getFontMetrics();
                g.setColor(isEnabled() ? (i == sel ? INK : INK2) : INK3);
                g.drawString(items[i], 3 + i * sw + (sw - fm.stringWidth(items[i])) / 2, (h + fm.getAscent() - fm.getDescent()) / 2);
            }
            g.dispose();
        }
    }

    /** Переключатель-тумблер. */
    static class Toggle extends JComponent {
        boolean on;
        final Consumer<Boolean> onChange;
        Toggle(boolean on, Consumer<Boolean> onChange) {
            this.on = on; this.onChange = onChange;
            setPreferredSize(new Dimension(44, 26));
            setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
            addMouseListener(new MouseAdapter() { @Override public void mouseClicked(MouseEvent e) { if (isEnabled()) set(!Toggle.this.on); } });
        }
        void set(boolean v) { on = v; onChange.accept(v); repaint(); }
        @Override protected void paintComponent(Graphics g0) {
            Graphics2D g = smooth(g0);
            g.setColor(on ? new Color(0x34C759) : new Color(0xD1D1D6));
            g.fill(new RoundRectangle2D.Double(0, 0, 44, 26, 26, 26));
            g.setColor(new Color(0, 0, 0, 30));
            g.fillOval(on ? 20 : 2, 3, 22, 22);
            g.setColor(Color.WHITE);
            g.fillOval(on ? 20 : 2, 2, 22, 22);
            g.dispose();
        }
    }

    /** График: коридор 10–90 %, прогноз (синий пунктир), факт (чёрный), подсказка при наведении. */
    class ChartPanel extends JPanel {
        int hover = -1;
        boolean busy;
        static final int L = 64, R = 18, T = 40, B = 40;

        ChartPanel() {
            setOpaque(false);
            MouseAdapter ma = new MouseAdapter() {
                @Override public void mouseMoved(MouseEvent e) {
                    if (rows.isEmpty()) return;
                    int h = (int) Math.round((e.getX() - L) / (double) (getWidth() - L - R) * 23);
                    hover = (h < 0 || h > 23) ? -1 : h;
                    repaint();
                }
                @Override public void mouseExited(MouseEvent e) { hover = -1; repaint(); }
            };
            addMouseMotionListener(ma);
            addMouseListener(ma);
        }

        @Override protected void paintComponent(Graphics g0) {
            Graphics2D g = smooth(g0);
            int W = getWidth(), H = getHeight(), r = W - R, b = H - B;
            g.setFont(new Font(FONT, Font.PLAIN, 12));
            FontMetrics fm = g.getFontMetrics();
            if (rows.isEmpty()) {
                g.setColor(INK3);
                g.setFont(new Font(FONT, Font.PLAIN, 15));
                String s = busy ? "Модель считает прогноз…" : "Нажмите «Сделать прогноз» — здесь появится почасовой график";
                g.drawString(s, (W - g.getFontMetrics().stringWidth(s)) / 2, H / 2);
                g.dispose();
                return;
            }
            double lo = Double.MAX_VALUE, hi = -Double.MAX_VALUE;
            for (Row row : rows) {
                lo = Math.min(lo, row.actual() == null ? row.p10() : Math.min(row.p10(), row.actual()));
                hi = Math.max(hi, row.actual() == null ? row.p90() : Math.max(row.p90(), row.actual()));
            }
            double step = (hi - lo) > 2500 ? 1000 : 500, ylo = Math.floor(lo / step) * step, yhi = Math.ceil(hi / step) * step;
            java.util.function.DoubleUnaryOperator Y = v -> b - (v - ylo) / (yhi - ylo) * (b - T);
            java.util.function.IntToDoubleFunction X = h -> L + h / 23.0 * (r - L);
            for (double v = ylo; v <= yhi + 1e-6; v += step) {
                int y = (int) Y.applyAsDouble(v);
                g.setColor(LINE); g.drawLine(L, y, r, y);
                g.setColor(INK3); String s = mw(v); g.drawString(s, L - 10 - fm.stringWidth(s), y + 4);
            }
            for (int h = 0; h < 24; h += 3) { String s = String.format("%02d:00", h); g.drawString(s, (int) X.applyAsDouble(h) - fm.stringWidth(s) / 2, b + 22); }

            Path2D band = new Path2D.Double();
            for (Row row : rows) { double x = X.applyAsDouble(row.hour()), y = Y.applyAsDouble(row.p90()); if (row.hour() == 0) band.moveTo(x, y); else band.lineTo(x, y); }
            for (int i = rows.size() - 1; i >= 0; i--) band.lineTo(X.applyAsDouble(rows.get(i).hour()), Y.applyAsDouble(rows.get(i).p10()));
            band.closePath();
            g.setColor(new Color(0, 113, 227, 34)); g.fill(band);
            Path2D fc = new Path2D.Double(), act = new Path2D.Double();
            boolean pen = false;
            for (Row row : rows) {
                double x = X.applyAsDouble(row.hour());
                if (row.hour() == 0) fc.moveTo(x, Y.applyAsDouble(row.fc())); else fc.lineTo(x, Y.applyAsDouble(row.fc()));
                if (row.actual() != null) { if (pen) act.lineTo(x, Y.applyAsDouble(row.actual())); else act.moveTo(x, Y.applyAsDouble(row.actual())); pen = true; } else pen = false;
            }
            g.setStroke(new BasicStroke(2.6f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND)); g.setColor(INK); g.draw(act);
            g.setStroke(new BasicStroke(2.6f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND, 10f, new float[]{7f, 5f}, 0f)); g.setColor(ACCENT); g.draw(fc);

            g.setStroke(new BasicStroke(1f));
            int lx = L, ly = 18;
            g.setColor(ACCENT); g.fillRoundRect(lx, ly - 5, 22, 3, 3, 3); g.setColor(INK2); g.drawString("прогноз", lx + 30, ly);
            lx += 104;
            g.setColor(new Color(0, 113, 227, 50)); g.fillRoundRect(lx, ly - 9, 22, 11, 4, 4); g.setColor(INK2); g.drawString("коридор 10–90 %", lx + 30, ly);
            lx += 156;
            if (rows.stream().anyMatch(x -> x.actual() != null)) { g.setColor(INK); g.fillRoundRect(lx, ly - 5, 22, 3, 3, 3); g.setColor(INK2); g.drawString("факт", lx + 30, ly); }
            g.setColor(INK3); g.drawString("МВт", 6, T - 16);

            if (hover >= 0) {
                Row row = rows.get(hover);
                int x = (int) X.applyAsDouble(hover);
                g.setColor(new Color(0, 0, 0, 40)); g.drawLine(x, T, x, b);
                int fy = (int) Y.applyAsDouble(row.fc());
                g.setColor(Color.WHITE); g.fillOval(x - 7, fy - 7, 14, 14); g.setColor(ACCENT); g.fillOval(x - 5, fy - 5, 10, 10);
                if (row.actual() != null) { int ay = (int) Y.applyAsDouble(row.actual()); g.setColor(Color.WHITE); g.fillOval(x - 7, ay - 7, 14, 14); g.setColor(INK); g.fillOval(x - 5, ay - 5, 10, 10); }
                List<String> lines = new ArrayList<>(List.of(String.format("%02d:00", row.hour()), "Прогноз  " + mw(row.fc()) + " МВт", "Коридор  " + mw(row.p10()) + "–" + mw(row.p90())));
                if (row.actual() != null) lines.add("Факт  " + mw(row.actual()) + " МВт");
                if (row.temp() != null) lines.add(String.format(RU, "Температура  %.1f °C", row.temp()));
                int bw = lines.stream().mapToInt(fm::stringWidth).max().orElse(80) + 24, bh = lines.size() * 19 + 14;
                int bx = x + 16 + bw > r ? x - 16 - bw : x + 16, by = T + 6;
                for (int i = 5; i >= 1; i--) { g.setColor(new Color(0, 0, 0, 5)); g.fillRoundRect(bx - i, by - i + 3, bw + 2 * i, bh + 2 * i, 18, 18); }
                g.setColor(Color.WHITE); g.fillRoundRect(bx, by, bw, bh, 14, 14);
                for (int i = 0; i < lines.size(); i++) {
                    g.setFont(new Font(FONT, i == 0 ? Font.BOLD : Font.PLAIN, 12));
                    g.setColor(i == 0 ? INK : INK2);
                    g.drawString(lines.get(i), bx + 12, by + 22 + i * 19);
                }
            }
            g.dispose();
        }
    }

    public static void main(String[] args) {
        System.setProperty("apple.awt.application.name", "Прогноз потребления");
        System.setProperty("apple.awt.application.appearance", "NSAppearanceNameAqua");
        File root = new File(args.length > 0 ? args[0] : System.getProperty("user.dir")).getAbsoluteFile();
        SwingUtilities.invokeLater(() -> {
            try { UIManager.setLookAndFeel(UIManager.getCrossPlatformLookAndFeelClassName()); } catch (Exception ignored) {}
            UIManager.put("ScrollBar.width", 8);
            new ForecastApp(root).setVisible(true);
        });
    }
}
