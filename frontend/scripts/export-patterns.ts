// 패턴 12종의 생성 코드를 백엔드 통합 테스트용 fixture 로 내보낸다.
//   node scripts/export-patterns.ts        (frontend 디렉터리에서)
// 생성기를 바꾼 뒤 실행해 fixture 를 갱신한다. vitest 가 fixture 와 생성 결과가 같은지 검사한다.
import { writeFileSync } from "node:fs";
import { buildPatternFixture, FIXTURE_PATH } from "../src/lib/playground/fixture.ts";

writeFileSync(FIXTURE_PATH, JSON.stringify(buildPatternFixture(), null, 2) + "\n");
console.log(`wrote ${FIXTURE_PATH}`);
