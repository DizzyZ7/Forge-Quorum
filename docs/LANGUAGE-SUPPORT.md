# Language and ecosystem support (v0.3.0)

ForgeQuorum packages **instructions and profiles**, not runtime compilers, IDEs or API keys. This table means there is a specialized agent or shared workflow for the technology—not that ForgeQuorum independently compiles it.

| Ecosystem | Profiles | Example role | What Codex should verify |
|---|---|---|---|
| Python, FastAPI, Django | `python`, `backend` | `python-backend` | virtualenv, lockfiles, typing, unit/integration tests |
| JS, TypeScript, Node, React/Vue | `node`, `web` | `node-backend`, `frontend-engineer` | package manager, framework, build and e2e |
| Java, Spring Boot | `java`, `backend` | `java-engineer` | JVM version, Maven/Gradle, persistence and tests |
| Kotlin, Ktor | `kotlin`, `mobile` | `kotlin-engineer` | coroutines, build scripts, platform contracts |
| Go | `go`, `backend` | `go-engineer` | contexts, race checks, go.mod, integration tests |
| Rust | `rust`, `systems` | `rust-engineer` | Cargo workspace, clippy, ownership, unsafe |
| C#, .NET | `dotnet`, `desktop` | `dotnet-engineer` | target frameworks, DI, solution build, tests |
| C and C++ | `systems`, `embedded` | `cpp-engineer`, `embedded-engineer` | CMake, ABI, sanitizers, target hardware |
| PHP / Ruby | `php`, `ruby`, `web` | `php-engineer`, `ruby-engineer` | Composer/Bundler, migrations, auth |
| Swift, iOS | `mobile` | `swift-engineer` | Xcode, entitlements, simulators, device checks |
| Dart, Flutter, Android | `mobile` | `flutter-engineer`, `android-engineer` | SDK versions, permissions, lifecycle, releases |
| Desktop: Qt/Electron/Tauri | `desktop` | `desktop-engineer` | OS/architecture, installers, resource use |
| Unity/Unreal/Godot | `games` | `game-engineer` | engine version, frame budgets, save state |
| SQL/Spark/dbt/Airflow | `data` | `data-engineer` | data quality, replay, schema and lineage |
| LLM/RAG, ML/MLOps | `ml` | `ml-engineer`, `mlops-engineer` | metrics, eval sets, drift and serving budgets |
| R/Julia/MATLAB | `scientific` | `scientific-engineer` | units, numerical stability, reproducibility |
| Scala/Elixir/Erlang/Haskell/F# | `functional` | `functional-engineer` | type contracts, concurrency, runtimes |
| Terraform/OpenTofu/Pulumi | `cloud` | `terraform-engineer` | safe plan/diff; explicit approval to apply |
| Kubernetes/Helm/GitOps | `cloud`, `infra` | `kubernetes-engineer`, `sre-engineer` | context, policies, rollout and rollback |
| Security, privacy, test tooling | `security`, `qa` | `security-auditor`, `privacy-engineer`, `qa-automation` | risk evidence, least privilege, actual results |

## Stack detection

`fq inspect --target PATH --json` inventories known file extensions and manifests without reading source contents. Examples include `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle.kts`, `package.json`, `*.csproj`, `composer.json`, `Gemfile`, `Package.swift`, `pubspec.yaml`, `CMakeLists.txt`, `project.godot`, and Terraform files.

Heuristic limitations:

- It does not parse configuration or prove dependencies are installed.
- It can misidentify mixed repos and nested language projects.
- It skips generated/dependency directories and symlinks.
- It caps the scan at 5,000 files (the underlying Python API supports configurable bounds).
- `--profile auto` resolves to a concrete profile and stores that profile in the manifest.

When in doubt, select a profile explicitly; `full` installs the entire catalog. For a truly unusual stack, the generic architect, explorer, reviewer, testing and system roles still give Codex relevant engineering constraints.
