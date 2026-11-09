use chrono::{DateTime, NaiveDate, SecondsFormat, Utc};
use rusqlite::{params, params_from_iter, types::Value as SqlValue, Connection, OptionalExtension};
use serde_json::{json, Value};

type R<T> = Result<T, String>;
fn err(e: impl std::fmt::Display) -> String {
    e.to_string()
}
pub fn init(db: &Connection) -> R<()> {
    db.execute_batch("PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY, tipo TEXT NOT NULL CHECK(tipo IN ('grupo','pasta','atividade')), titulo TEXT NOT NULL, descricao TEXT, prazo TEXT, concluida INTEGER NOT NULL DEFAULT 0, pai_id INTEGER REFERENCES items(id) ON DELETE CASCADE, criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP); CREATE INDEX IF NOT EXISTS idx_items_pai ON items(pai_id); CREATE INDEX IF NOT EXISTS idx_items_prazo ON items(prazo);").map_err(err)?;
    let has_reminder: bool = db
        .query_row(
            "SELECT EXISTS(SELECT 1 FROM pragma_table_info('items') WHERE name='lembrete_utc')",
            [],
            |r| r.get(0),
        )
        .map_err(err)?;
    if !has_reminder {
        db.execute("ALTER TABLE items ADD COLUMN lembrete_utc TEXT", [])
            .map_err(err)?;
    }
    let has_tags: bool = db
        .query_row(
            "SELECT EXISTS(SELECT 1 FROM pragma_table_info('items') WHERE name='tags')",
            [],
            |r| r.get(0),
        )
        .map_err(err)?;
    if !has_tags {
        db.execute(
            "ALTER TABLE items ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'",
            [],
        )
        .map_err(err)?;
    }
    Ok(())
}
fn id(a: &Value) -> R<i64> {
    a.get("id")
        .and_then(Value::as_i64)
        .filter(|n| *n > 0)
        .ok_or("id inválido".into())
}
fn title(v: &Value) -> R<&str> {
    v.as_str()
        .map(str::trim)
        .filter(|s| !s.is_empty() && s.chars().count() <= 500)
        .ok_or("título deve conter de 1 a 500 caracteres".into())
}
fn opt_text(v: Option<&Value>, field: &str) -> R<Option<String>> {
    match v {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(s)) if s.len() <= 20000 => Ok(Some(s.clone())),
        _ => Err(format!("{field} inválida ou longa demais")),
    }
}
fn date(v: Option<&Value>) -> R<Option<String>> {
    let Some(s) = opt_text(v, "prazo")? else {
        return Ok(None);
    };
    let d = NaiveDate::parse_from_str(&s, "%d/%m/%Y")
        .map_err(|_| "prazo inválido: use DD/MM/AAAA".to_string())?;
    if d.format("%d/%m/%Y").to_string() != s {
        return Err("prazo inválido: use DD/MM/AAAA".into());
    }
    Ok(Some(d.format("%Y-%m-%d").to_string()))
}
fn reminder(v: Option<&Value>) -> R<Option<String>> {
    let Some(s) = opt_text(v, "lembrete")? else {
        return Ok(None);
    };
    let dt = DateTime::parse_from_rfc3339(&s)
        .map_err(|_| "lembrete inválido: use data e hora ISO 8601 com fuso".to_string())?;
    Ok(Some(
        dt.with_timezone(&Utc)
            .to_rfc3339_opts(SecondsFormat::Secs, true),
    ))
}
fn tags(v: Option<&Value>) -> R<String> {
    let list = match v {
        None | Some(Value::Null) => vec![],
        Some(Value::Array(a)) if a.len() <= 12 => a.clone(),
        _ => return Err("tags devem ser uma lista com até 12 nomes".into()),
    };
    let mut names: Vec<String> = Vec::new();
    for value in list {
        let name = value
            .as_str()
            .map(str::trim)
            .filter(|x| !x.is_empty() && x.chars().count() <= 32 && !x.contains(','))
            .ok_or("tag inválida (use até 32 caracteres, sem vírgulas)")?;
        if !names.iter().any(|x| x.eq_ignore_ascii_case(name)) {
            names.push(name.to_string());
        }
    }
    serde_json::to_string(&names).map_err(err)
}
fn json_tags(value: String) -> Value {
    serde_json::from_str(&value).unwrap_or_else(|_| json!([]))
}
fn parent(v: Option<&Value>) -> R<Option<i64>> {
    match v {
        None | Some(Value::Null) => Ok(None),
        Some(n) => n
            .as_i64()
            .filter(|x| *x > 0)
            .map(Some)
            .ok_or("pai_id inválido".into()),
    }
}
fn kind(db: &Connection, id: i64) -> R<String> {
    db.query_row("SELECT tipo FROM items WHERE id=?1", [id], |r| r.get(0))
        .optional()
        .map_err(err)?
        .ok_or("item não encontrado".into())
}
fn validate_parent(db: &Connection, t: &str, p: Option<i64>, self_id: Option<i64>) -> R<()> {
    if let Some(p) = p {
        let pt = kind(db, p)?;
        if !matches!(
            (t, pt.as_str()),
            ("pasta", "grupo" | "pasta") | ("atividade", "pasta" | "atividade")
        ) {
            return Err(
                "hierarquia inválida: pasta em grupo/pasta; atividade em pasta/atividade".into(),
            );
        }
        if let Some(id) = self_id {
            let cycle:bool=db.query_row("WITH RECURSIVE descendants(id) AS (SELECT ?1 UNION SELECT items.id FROM items JOIN descendants ON items.pai_id=descendants.id) SELECT EXISTS(SELECT 1 FROM descendants WHERE id=?2)",params![id,p],|r|r.get(0)).map_err(err)?;
            if cycle {
                return Err("não é possível mover item para si ou descendente".into());
            }
        }
    }
    Ok(())
}
fn row(r: &rusqlite::Row<'_>) -> rusqlite::Result<Value> {
    let due: Option<String> = r.get(4)?;
    Ok(
        json!({"id":r.get::<_,i64>(0)?,"tipo":r.get::<_,String>(1)?,"titulo":r.get::<_,String>(2)?,"descricao":r.get::<_,Option<String>>(3)?,"prazo":due.and_then(|d|NaiveDate::parse_from_str(&d,"%Y-%m-%d").ok()).map(|d|d.format("%d/%m/%Y").to_string()),"concluida":r.get::<_,bool>(5)?,"pai_id":r.get::<_,Option<i64>>(6)?,"criado_em_utc":r.get::<_,String>(7)?,"atualizado_em_utc":r.get::<_,String>(8)?,"lembrete_utc":r.get::<_,Option<String>>(9)?,"tags":json_tags(r.get::<_,String>(10)?)}),
    )
}
const COL: &str =
    "id,tipo,titulo,descricao,prazo,concluida,pai_id,criado_em,atualizado_em,lembrete_utc,tags";
fn get(db: &Connection, n: i64) -> R<Value> {
    db.query_row(&format!("SELECT {COL} FROM items WHERE id=?1"), [n], row)
        .optional()
        .map_err(err)?
        .ok_or("item não encontrado".into())
}
pub fn call(db: &mut Connection, name: &str, a: &Value) -> R<Value> {
    if !a.is_object() {
        return Err("argumentos devem ser um objeto".into());
    }
    match name {
        "criar_item" => {
            let t = a
                .get("tipo")
                .and_then(Value::as_str)
                .filter(|s| ["grupo", "pasta", "atividade"].contains(s))
                .ok_or("tipo inválido")?;
            let ti = title(a.get("titulo").unwrap_or(&Value::Null))?;
            let p = parent(a.get("pai_id"))?;
            validate_parent(db, t, p, None)?;
            let desc = opt_text(a.get("descricao"), "descrição")?;
            let d = date(a.get("prazo"))?;
            let reminder = reminder(a.get("lembrete_utc"))?;
            let tags = tags(a.get("tags"))?;
            if t != "atividade" && (d.is_some() || reminder.is_some() || tags != "[]") {
                return Err("prazo é exclusivo de atividades".into());
            }
            db.execute(
                "INSERT INTO items(tipo,titulo,descricao,prazo,pai_id,lembrete_utc,tags) VALUES(?1,?2,?3,?4,?5,?6,?7)",
                params![t, ti, desc, d, p, reminder, tags],
            )
            .map_err(err)?;
            get(db, db.last_insert_rowid())
        }
        "obter_item" => {
            let n = id(a)?;
            let item = get(db, n)?;
            let (children, next) =
                list(db, Some(n), None, None, None, limit(a)?, cursor(a)?, false)?;
            Ok(json!({"item":item,"filhos":children,"proximo_cursor":next}))
        }
        "listar_itens" => {
            let p = parent(a.get("pai_id"))?;
            let t = opt_text(a.get("tipo"), "tipo")?;
            if let Some(ref t) = t {
                if !["grupo", "pasta", "atividade"].contains(&t.as_str()) {
                    return Err("tipo inválido".into());
                }
            }
            let done = match a.get("concluida") {
                None => None,
                Some(Value::Bool(b)) => Some(*b),
                _ => return Err("concluida inválida".into()),
            };
            let q = opt_text(a.get("busca"), "busca")?;
            let details = match a.get("detalhes") {
                None => false,
                Some(Value::Bool(b)) => *b,
                _ => return Err("detalhes inválido".into()),
            };
            let lim = limit(a)?;
            let (items, next) = list(db, p, t, done, q, lim, cursor(a)?, details)?;
            Ok(json!({"itens":items,"limite":lim,"proximo_cursor":next}))
        }
        "atualizar_item" => {
            let n = id(a)?;
            let t = kind(db, n)?;
            let old = get(db, n)?;
            let ti = if let Some(v) = a.get("titulo") {
                title(v)?.to_string()
            } else {
                old["titulo"].as_str().unwrap().to_string()
            };
            let desc = if a.get("descricao").is_some() {
                opt_text(a.get("descricao"), "descrição")?
            } else {
                old["descricao"].as_str().map(str::to_string)
            };
            let d = if a.get("prazo").is_some() {
                date(a.get("prazo"))?
            } else {
                date(old.get("prazo"))?
            };
            let reminder = if a.get("lembrete_utc").is_some() {
                reminder(a.get("lembrete_utc"))?
            } else {
                old["lembrete_utc"].as_str().map(str::to_string)
            };
            let tags = if a.get("tags").is_some() {
                tags(a.get("tags"))?
            } else {
                old["tags"].to_string()
            };
            let p = if a.get("pai_id").is_some() {
                parent(a.get("pai_id"))?
            } else {
                old["pai_id"].as_i64()
            };
            validate_parent(db, &t, p, Some(n))?;
            let done = if let Some(v) = a.get("concluida") {
                v.as_bool().ok_or("concluida inválida")?
            } else {
                old["concluida"].as_bool().unwrap()
            };
            if t != "atividade" && (d.is_some() || done || reminder.is_some() || tags != "[]") {
                return Err("prazo e conclusão são exclusivos de atividades".into());
            }
            db.execute("UPDATE items SET titulo=?1,descricao=?2,prazo=?3,pai_id=?4,concluida=?5,lembrete_utc=?6,tags=?7,atualizado_em=CURRENT_TIMESTAMP WHERE id=?8",params![ti,desc,d,p,done,reminder,tags,n]).map_err(err)?;
            get(db, n)
        }
        "excluir_item" => {
            let n = id(a)?;
            if a.get("confirmar") != Some(&Value::Bool(true)) {
                return Err("exclusão exige confirmar=true".into());
            }
            let item = get(db, n)?;
            let count:i64=db.query_row("WITH RECURSIVE descendants(id) AS (SELECT ?1 UNION ALL SELECT items.id FROM items JOIN descendants ON items.pai_id=descendants.id) SELECT COUNT(*) FROM descendants",[n],|r|r.get(0)).map_err(err)?;
            db.execute("DELETE FROM items WHERE id=?1", [n])
                .map_err(err)?;
            Ok(json!({"excluido":item,"total_excluido_incluindo_descendentes":count}))
        }
        _ => Err("ferramenta desconhecida".into()),
    }
}

fn limit(a: &Value) -> R<i64> {
    a.get("limite")
        .map(|v| {
            v.as_i64()
                .filter(|n| *n >= 1 && *n <= 500)
                .ok_or("limite inválido".to_string())
        })
        .transpose()
        .map(|x| x.unwrap_or(20))
}
fn cursor(a: &Value) -> R<i64> {
    a.get("cursor")
        .map(|v| {
            v.as_i64()
                .filter(|n| *n >= 0)
                .ok_or("cursor inválido".to_string())
        })
        .transpose()
        .map(|x| x.unwrap_or(0))
}
fn list(
    db: &Connection,
    p: Option<i64>,
    t: Option<String>,
    done: Option<bool>,
    q: Option<String>,
    limit: i64,
    cursor: i64,
    details: bool,
) -> R<(Vec<Value>, Option<i64>)> {
    let cols = if details {
        COL
    } else {
        "id,tipo,titulo,prazo,concluida,pai_id,lembrete_utc,tags"
    };
    let mut sql = format!("SELECT {cols} FROM items WHERE id > ?");
    let mut values = vec![SqlValue::Integer(cursor)];
    if let Some(p) = p {
        sql.push_str(" AND pai_id = ?");
        values.push(SqlValue::Integer(p));
    }
    if let Some(t) = t {
        sql.push_str(" AND tipo = ?");
        values.push(SqlValue::Text(t));
    }
    if let Some(done) = done {
        sql.push_str(" AND concluida = ?");
        values.push(SqlValue::Integer(done as i64));
    }
    if let Some(q) = q {
        sql.push_str(" AND instr(lower(titulo || ' ' || coalesce(descricao,'')),lower(?)) > 0");
        values.push(SqlValue::Text(q));
    }
    sql.push_str(" ORDER BY id LIMIT ?");
    values.push(SqlValue::Integer(limit + 1));
    let mut st = db.prepare_cached(&sql).map_err(err)?;
    let mut items = st
        .query_map(params_from_iter(values.iter()), |r| {
            if details {
                row(r)
            } else {
                summary_row(r)
            }
        })
        .map_err(err)?
        .collect::<Result<Vec<_>, _>>()
        .map_err(err)?;
    let next = if items.len() > limit as usize {
        items.pop();
        items.last().and_then(|v| v["id"].as_i64())
    } else {
        None
    };
    Ok((items, next))
}
fn summary_row(r: &rusqlite::Row<'_>) -> rusqlite::Result<Value> {
    let due: Option<String> = r.get(3)?;
    Ok(
        json!({"id":r.get::<_,i64>(0)?,"tipo":r.get::<_,String>(1)?,"titulo":r.get::<_,String>(2)?,"prazo":due.and_then(|d|NaiveDate::parse_from_str(&d,"%Y-%m-%d").ok()).map(|d|d.format("%d/%m/%Y").to_string()),"concluida":r.get::<_,bool>(4)?,"pai_id":r.get::<_,Option<i64>>(5)?,"lembrete_utc":r.get::<_,Option<String>>(6)?,"tags":json_tags(r.get::<_,String>(7)?)}),
    )
}
