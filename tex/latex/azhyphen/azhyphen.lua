-- azhyphen.lua -- standalone Azerbaijani hyphenation for LuaTeX
-- LPPL 1.3c or later; maintained by Anar Abdullayev. See LICENSE.

local cached = package.loaded.azhyphen
if type(cached) == "table" and type(cached.activate) == "function" then
  return cached
end

local M = {}

-- Conservative project defaults, pending linguistic review.
local LEFT_HYPHEN_MIN = 2
local RIGHT_HYPHEN_MIN = 2

local language_object
local language_id
local initialized = false

local case_pairs = {
  { "a", "A" }, { "b", "B" }, { "c", "C" }, { "ç", "Ç" },
  { "d", "D" }, { "e", "E" }, { "ə", "Ə" }, { "f", "F" },
  { "g", "G" }, { "ğ", "Ğ" }, { "h", "H" },
  -- Azerbaijani has two distinct I pairs; do not use locale-neutral mapping.
  { "i", "İ" }, { "ı", "I" },
  { "j", "J" }, { "k", "K" }, { "q", "Q" }, { "l", "L" },
  { "m", "M" }, { "n", "N" }, { "o", "O" }, { "ö", "Ö" },
  { "p", "P" }, { "r", "R" }, { "s", "S" }, { "ş", "Ş" },
  { "t", "T" }, { "u", "U" }, { "ü", "Ü" }, { "v", "V" },
  { "x", "X" }, { "y", "Y" }, { "z", "Z" },
}

local function read_data_file(name, required)
  local path = kpse.find_file(name, "tex")
  if not path then
    if required then
      error("required pattern file " .. name .. " was not found by kpathsea", 0)
    end
    return nil
  end

  local handle, open_error = io.open(path, "rb")
  if not handle then
    error("cannot read " .. path .. ": " .. tostring(open_error), 0)
  end
  local data = handle:read("*a")
  handle:close()
  if not data then
    error("cannot read data from " .. path, 0)
  end

  -- PATGEN output is whitespace-separated. Permit TeX-style comment lines and
  -- an optional UTF-8 BOM without passing either to LuaTeX's pattern parser.
  data = data:gsub("^\239\187\191", "")
  data = data:gsub("%%[^\r\n]*", "")
  if not data:find("%S") then
    if required then
      error("required pattern file " .. path .. " is empty", 0)
    end
    return nil
  end
  return data, path
end

local function configure_hjcodes(object)
  for _, pair in ipairs(case_pairs) do
    local lower = utf8.codepoint(pair[1])
    local upper = utf8.codepoint(pair[2])
    lang.sethjcode(object, lower, lower)
    lang.sethjcode(object, upper, lower)
  end
end

local function validate_patterns(patterns, path)
  local token_count = 0
  for token in patterns:gmatch("%S+") do
    token_count = token_count + 1
    local has_digit = false
    if not utf8.len(token) then
      error("pattern data in " .. path .. " is not valid UTF-8", 0)
    end
    if token:find("[\\{}]") then
      error("invalid pattern token in " .. path .. ": " .. token, 0)
    end
    if token:find("[0-9]") then
      has_digit = true
    end
    if not has_digit then
      error("invalid PATGEN pattern token in " .. path .. ": " .. token, 0)
    end
  end
  if token_count == 0 then
    error("required pattern file " .. path .. " is empty", 0)
  end
end

local function initialize()
  if initialized then
    return
  end

  local patterns, pattern_path = read_data_file("azhyphen.pat.txt", true)
  local exceptions = read_data_file("azhyphen.hyp.txt", false)
  validate_patterns(patterns, pattern_path)

  if not language_object then
    language_object = lang.new()
    language_id = lang.id(language_object)
    configure_hjcodes(language_object)
  end

  local patterns_ok, patterns_error = pcall(lang.patterns, language_object, patterns)
  if not patterns_ok then
    error("invalid patterns in " .. pattern_path .. ": " ..
      tostring(patterns_error), 0)
  end
  local installed_patterns = lang.patterns(language_object)
  if type(installed_patterns) ~= "string" or not installed_patterns:find("%S") then
    error("LuaTeX accepted no patterns from " .. pattern_path, 0)
  end

  if exceptions then
    local exceptions_ok, exceptions_error = pcall(
      lang.hyphenation, language_object, exceptions
    )
    if not exceptions_ok then
      error("invalid exceptions in azhyphen.hyp.txt: " ..
        tostring(exceptions_error), 0)
    end
  end

  initialized = true
end

function M.activate()
  initialize()
  tex.set("global", "language", language_id)
  tex.set("global", "lefthyphenmin", LEFT_HYPHEN_MIN)
  tex.set("global", "righthyphenmin", RIGHT_HYPHEN_MIN)
  return language_id
end

package.loaded.azhyphen = M
return M
