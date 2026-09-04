# BULKWATCH 2027

Logan → 170 lb. Felix → 165 lb. Deadline: **March 1, 2027.**

Site: https://logan.valeski.org/bulkwatch/

## Easiest: email it in

Email your Mist CSV export to **bulkwatch@in.river.page** (from the email
address registered in `senders.json`). You can also weigh in with no
attachment at all — just put e.g. `weight 152.5` in the subject line.
A robot checks the mailbox every 30 minutes and updates the site.

## Or upload through GitHub

1. In Mist, export your CSV.
2. On github.com, open `inbox/logan/` or `inbox/felix/` (whichever is you).
3. **Add file → Upload files**, drop the CSV, commit.
4. A robot merges it and the site updates in ~1 minute.

Re-uploading old dates is fine — an export that overlaps a previous one just
replaces those days with the newer data. You never have to trim a CSV.

## How to log your weight

Edit `data/logan_weight.csv` or `data/felix_weight.csv` right on github.com
(pencil icon) and add a line:

```
2026-09-02,152.5
```

One line per weigh-in, `YYYY-MM-DD,pounds`. Same date twice = last one wins.

## Local (Logan's) shortcut

```
python3 merge.py logan ~/Downloads/mist_export.csv
python3 merge.py logan --weight 152.5
git add -A && git commit -m gainz && git push
```

## Rules

- 2600+ calories = a green day. Anything less is red and everyone can see it.
- No logging is worse than a red day. Gray squares are shameful.
- The chart does not negotiate.
