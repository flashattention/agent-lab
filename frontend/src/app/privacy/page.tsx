import type { Metadata } from "next";
import { CONTACT_URL, LegalPage } from "@/components/legal/legal-page";

export const metadata: Metadata = { title: "개인정보처리방침" };

export default function PrivacyPage() {
  return (
    <LegalPage title="개인정보처리방침">
      <p>
        AgentLab(이하 &ldquo;서비스&rdquo;)은 AI Agent 학습을 위한 비상업적 개인 프로젝트입니다. 서비스는 운영에 꼭 필요한 최소한의 정보만
        처리하며, 수집한 정보를 판매하거나 광고에 사용하지 않습니다.
      </p>

      <section>
        <h2>1. 수집하는 정보</h2>
        <ul>
          <li>
            <strong>Google 로그인 정보:</strong> Google 계정으로 로그인하면 이메일 주소, 이름, 프로필 사진, 계정 고유 ID를 받습니다. 그 밖의
            Google 데이터(Gmail, Drive, 연락처 등)에는 접근하지 않습니다.
          </li>
          <li>
            <strong>저장한 프로젝트:</strong> 플레이그라운드에서 &ldquo;프로젝트로 저장&rdquo;한 그래프, 코드, 프로젝트 이름, 공개 여부, 생성·수정
            시각.
          </li>
        </ul>
      </section>

      <section>
        <h2>2. 저장하지 않는 정보</h2>
        <ul>
          <li>
            <strong>OpenAI API 키:</strong> 이 브라우저(localStorage)에만 저장됩니다. 코드를 실행할 때만 서버로 전달되며, 서버는 키를 저장하거나
            기록하지 않습니다.
          </li>
          <li>
            <strong>실행한 코드와 결과:</strong> 실행 요청을 처리하는 동안에만 서버 메모리에 머물고 저장되지 않습니다. 단, &ldquo;고도화&rdquo;
            기능으로 검증된 코드는 같은 구조의 요청에 재사용하기 위해 사용자 정보 없이 캐시될 수 있습니다.
          </li>
          <li>강의 실습 코드와 작업 중인 플레이그라운드는 이 브라우저(localStorage)에만 저장됩니다.</li>
        </ul>
      </section>

      <section>
        <h2>3. 이용 목적</h2>
        <ul>
          <li>로그인 상태 유지와 본인 확인</li>
          <li>프로젝트 저장, 불러오기, 공유 링크 제공</li>
          <li>사용자별 하루 실행 한도 적용 (서버 메모리에 횟수만 일시 기록)</li>
        </ul>
      </section>

      <section>
        <h2>4. 처리 위탁</h2>
        <p>서비스는 다음 업체의 인프라를 이용합니다.</p>
        <ul>
          <li>
            <strong>Supabase:</strong> 로그인 처리와 프로젝트 저장 (데이터베이스 리전: 서울)
          </li>
          <li>
            <strong>Google Cloud:</strong> 코드 실행 서버 (리전: 서울)
          </li>
          <li>
            <strong>Vercel:</strong> 웹사이트 호스팅
          </li>
          <li>
            <strong>OpenAI:</strong> 코드 실행 시 사용자가 입력한 본인 API 키로 직접 호출됩니다.
          </li>
        </ul>
      </section>

      <section>
        <h2>5. 공유</h2>
        <p>
          프로젝트는 기본적으로 본인만 볼 수 있습니다. 직접 &ldquo;공유&rdquo;를 켠 프로젝트만 링크를 가진 사람이 볼 수 있으며, 언제든 다시 끌 수
          있습니다.
        </p>
      </section>

      <section>
        <h2>6. 보관과 삭제</h2>
        <p>
          저장한 프로젝트는 직접 삭제할 때까지 보관됩니다. 계정과 모든 데이터 삭제를 원하면 아래 연락처로 요청해 주세요. 요청을 받으면 지체 없이
          삭제합니다.
        </p>
      </section>

      <section>
        <h2>7. 문의</h2>
        <p>
          개인정보 관련 문의와 삭제 요청은 <a href={CONTACT_URL}>GitHub Issues</a>로 보내 주세요.
        </p>
      </section>
    </LegalPage>
  );
}
